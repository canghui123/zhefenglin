"""Task 10 — standardized error envelope.

All business errors must return the envelope::

    {
      "error": {
        "code": "ASSET_PACKAGE_NOT_FOUND",
        "message": "资产包不存在",
        "request_id": "...",
        "details": {}
      }
    }
"""
from fastapi.testclient import TestClient

from main import app
from db.session import get_db_session
from repositories import user_repo, tenant_repo
from services.password_service import hash_password


def _seed_and_login(client: TestClient):
    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_or_create_tenant(
            session, code="err", name="Error Tenant"
        )
        user = user_repo.create_user(
            session,
            email="err@example.com",
            password_hash=hash_password("Passw0rd!"),
            role="operator",
            display_name="err",
        )
        tenant_repo.create_membership(session, user_id=user.id, tenant_id=tenant.id)
        user_repo.set_default_tenant(session, user.id, tenant.id)
        session.commit()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    client.post(
        "/api/auth/login",
        json={"email": "err@example.com", "password": "Passw0rd!"},
    )


def test_not_found_returns_standard_envelope():
    client = TestClient(app)
    _seed_and_login(client)

    r = client.get("/api/asset-package/999999")
    assert r.status_code == 404
    body = r.json()
    assert "error" in body
    err = body["error"]
    assert err["code"] == "ASSET_PACKAGE_NOT_FOUND"
    assert "message" in err
    assert "request_id" in err


def test_validation_error_returns_standard_envelope():
    client = TestClient(app)
    _seed_and_login(client)

    r = client.post(
        "/api/asset-package/calculate",
        json={},  # missing required fields
    )
    assert r.status_code == 422
    body = r.json()
    assert "error" in body
    err = body["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert "request_id" in err


def test_auth_error_returns_standard_envelope():
    client = TestClient(app)
    r = client.get("/api/asset-package/list/all")
    assert r.status_code == 401
    body = r.json()
    assert "error" in body
    assert body["error"]["code"] == "UNAUTHORIZED"
