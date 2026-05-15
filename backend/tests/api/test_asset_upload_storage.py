"""Task 7 — upload goes through storage service, not raw disk.

The test seeds a user, uploads an Excel via the API, and checks that:
1. The response still returns a valid package_id (backward compat).
2. The storage service received the bytes (via get_bytes round-trip).
3. The DB row has a `storage_key` instead of relying on a bare filename.
4. The authorized download endpoint serves the file back with a 200.
"""
import os
import io
import sys

from fastapi.testclient import TestClient

from config import settings
from main import app
from db.session import get_db_session
from repositories import user_repo, tenant_repo, asset_package_repo
from services.password_service import hash_password
from services.storage.factory import get_storage, reset_storage


SAMPLE_EXCEL = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "sample_asset_package.xlsx"
)


class _FakeS3Client:
    class exceptions:
        class ClientError(Exception):
            pass

    def __init__(self):
        self.objects: dict[str, bytes] = {}

    def head_bucket(self, Bucket: str):
        return None

    def create_bucket(self, Bucket: str):
        return None

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str):
        self.objects[Key] = Body

    def get_object(self, *, Bucket: str, Key: str):
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, *, Bucket: str, Key: str):
        self.objects.pop(Key, None)

    def generate_presigned_url(self, operation: str, *, Params: dict, ExpiresIn: int):
        return (
            f"http://minio:9000/{Params['Bucket']}/{Params['Key']}"
            f"?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Expires={ExpiresIn}"
        )


class _FakeBoto3Module:
    def __init__(self, client: _FakeS3Client):
        self._client = client

    def client(self, service_name: str, **kwargs):
        assert service_name == "s3"
        return self._client


def _use_fake_s3_storage(monkeypatch) -> _FakeS3Client:
    fake_client = _FakeS3Client()
    monkeypatch.setitem(sys.modules, "boto3", _FakeBoto3Module(fake_client))
    monkeypatch.setattr(settings, "storage_backend", "s3", raising=False)
    monkeypatch.setattr(settings, "s3_endpoint", "http://minio:9000", raising=False)
    monkeypatch.setattr(settings, "s3_bucket", "auto-finance", raising=False)
    monkeypatch.setattr(settings, "s3_access_key", "minioadmin", raising=False)
    monkeypatch.setattr(settings, "s3_secret_key", "minioadmin", raising=False)
    monkeypatch.setattr(settings, "s3_public_base_url", "", raising=False)
    reset_storage()
    return fake_client


def _seed_and_login(client: TestClient) -> int:
    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_or_create_tenant(
            session, code="storage", name="Storage Tenant"
        )
        user = user_repo.create_user(
            session,
            email="storage@example.com",
            password_hash=hash_password("Passw0rd!1"),
            role="operator",
            display_name="storage",
        )
        tenant_repo.create_membership(session, user_id=user.id, tenant_id=tenant.id)
        user_repo.set_default_tenant(session, user.id, tenant.id)
        session.commit()
        uid = user.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    r = client.post(
        "/api/auth/login",
        json={"email": "storage@example.com", "password": "Passw0rd!1"},
    )
    assert r.status_code == 200
    return uid


def test_upload_stores_file_via_storage_service():
    client = TestClient(app)
    _seed_and_login(client)

    with open(SAMPLE_EXCEL, "rb") as f:
        raw_bytes = f.read()

    with open(SAMPLE_EXCEL, "rb") as f:
        resp = client.post(
            "/api/asset-package/upload",
            files={
                "file": (
                    "storage_test.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert resp.status_code == 200, resp.text
    package_id = resp.json()["package_id"]

    # The DB row must have a storage_key
    gen = get_db_session()
    session = next(gen)
    try:
        pkg = asset_package_repo.get_package_by_id(
            session, package_id, tenant_id=1  # seeded tenant
        )
        assert pkg is not None
        assert pkg.storage_key, "storage_key should be set"
        key = pkg.storage_key
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    # Round-trip: the storage backend can return the same bytes
    store = get_storage()
    stored = store.get_bytes(key)
    assert stored == raw_bytes


def test_download_endpoint_serves_file():
    client = TestClient(app)
    _seed_and_login(client)

    with open(SAMPLE_EXCEL, "rb") as f:
        up = client.post(
            "/api/asset-package/upload",
            files={
                "file": (
                    "dl_test.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert up.status_code == 200
    package_id = up.json()["package_id"]

    dl = client.get(f"/api/asset-package/{package_id}/download")
    assert dl.status_code == 200
    assert dl.headers["content-type"] in (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/octet-stream",
    )
    assert len(dl.content) > 0


def test_download_endpoint_proxies_file_when_s3_has_no_public_base(monkeypatch):
    _use_fake_s3_storage(monkeypatch)
    client = TestClient(app)
    _seed_and_login(client)

    with open(SAMPLE_EXCEL, "rb") as f:
        raw_bytes = f.read()

    with open(SAMPLE_EXCEL, "rb") as f:
        up = client.post(
            "/api/asset-package/upload",
            files={
                "file": (
                    "s3_dl_test.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert up.status_code == 200, up.text
    package_id = up.json()["package_id"]

    dl = client.get(
        f"/api/asset-package/{package_id}/download",
        follow_redirects=False,
    )
    assert dl.status_code == 200, dl.text
    assert "location" not in {k.lower(): v for k, v in dl.headers.items()}
    assert dl.content == raw_bytes
