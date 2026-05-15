import io
import sys

from config import settings
from services.storage.factory import reset_storage
from services.storage.s3 import S3Storage


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


def _install_fake_s3(monkeypatch) -> _FakeS3Client:
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


def test_s3_storage_with_internal_only_endpoint_does_not_publish_download_url(monkeypatch):
    _install_fake_s3(monkeypatch)

    store = S3Storage()

    assert store.build_download_url("reports/sandbox_1.html") is None


def test_s3_storage_rewrites_download_url_to_public_base(monkeypatch):
    _install_fake_s3(monkeypatch)
    monkeypatch.setattr(
        settings,
        "s3_public_base_url",
        "https://files.example.com",
        raising=False,
    )

    store = S3Storage()

    url = store.build_download_url("reports/sandbox_1.html", expires_in=600)

    assert url is not None
    assert url.startswith("https://files.example.com/auto-finance/reports/sandbox_1.html")
    assert "X-Amz-Expires=600" in url
