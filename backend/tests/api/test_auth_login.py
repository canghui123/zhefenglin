"""Auth login flow — Task 5 Step 1.

These tests describe the contract:
- POST /api/auth/login with valid credentials returns 200 + an access token
  and sets a session cookie.
- POST /api/auth/login with bad credentials returns 401.
- GET /api/auth/me with the session cookie returns the current user.
"""
from fastapi.testclient import TestClient

from main import app
from db.session import get_db_session
from repositories import tenant_repo, user_repo
from services.password_service import hash_password


def _seed_user(email="admin@example.com", password="Passw0rd!", role="admin"):
    gen = get_db_session()
    session = next(gen)
    try:
        user = user_repo.create_user(
            session,
            email=email,
            password_hash=hash_password(password),
            role=role,
            display_name="Admin",
        )
        session.commit()
        return user.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_login_with_valid_credentials_returns_token_and_cookie():
    _seed_user()
    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "Passw0rd!"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "access_token" in body
    assert body["user"]["email"] == "admin@example.com"
    assert body["user"]["role"] == "admin"
    # Cookie was set on the response
    assert any(
        c.lower().startswith("set-cookie") for c in response.headers.keys()
    ) or "session" in (response.cookies or {})


def test_login_with_wrong_password_returns_401():
    _seed_user()
    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_login_with_unknown_user_returns_401():
    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={"email": "ghost@example.com", "password": "anything"},
    )

    assert response.status_code == 401


def test_me_endpoint_requires_session_and_returns_user():
    _seed_user()
    client = TestClient(app)

    # Without auth → 401
    anon = client.get("/api/auth/me")
    assert anon.status_code == 401

    # With session cookie → 200
    login = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "Passw0rd!"},
    )
    assert login.status_code == 200

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "admin@example.com"


def test_register_assigns_default_tenant_membership_and_session():
    client = TestClient(app)

    response = client.post(
        "/api/auth/register",
        json={
            "email": "new-user@example.com",
            "password": "Passw0rd!",
            "display_name": "New User",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["email"] == "new-user@example.com"
    assert body["user"]["role"] == "viewer"
    assert any(
        c.lower().startswith("set-cookie") for c in response.headers.keys()
    ) or "session" in (response.cookies or {})

    gen = get_db_session()
    session = next(gen)
    try:
        user = user_repo.get_user_by_email(session, "new-user@example.com")
        assert user is not None
        assert user.default_tenant_id is not None

        default_tenant = tenant_repo.get_tenant_by_code(session, "default")
        assert default_tenant is not None
        assert user.default_tenant_id == default_tenant.id
        assert tenant_repo.has_membership(
            session, user_id=user.id, tenant_id=default_tenant.id
        )
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_register_blocks_when_default_tenant_seat_limit_is_exhausted():
    from sqlalchemy import select

    from db.models.plan import Plan
    from db.models.subscription import TenantSubscription
    from scripts.seed_commercial_defaults import seed_defaults

    gen = get_db_session()
    session = next(gen)
    try:
        seed_defaults(session)
        default_tenant = tenant_repo.get_or_create_tenant(
            session, code="default", name="默认租户"
        )
        plan = session.scalars(
            select(Plan).where(Plan.code == "standard").limit(1)
        ).first()
        assert plan is not None
        plan.seat_limit = 1
        session.add(
            TenantSubscription(
                tenant_id=default_tenant.id,
                plan_id=plan.id,
                status="active",
                monthly_budget_limit=5000,
                alert_threshold_percent=80,
                is_current=True,
            )
        )
        session.commit()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    client = TestClient(app)

    first = client.post(
        "/api/auth/register",
        json={
            "email": "seat-first@example.com",
            "password": "Passw0rd!",
            "display_name": "Seat First",
        },
    )
    assert first.status_code == 200, first.text

    second = client.post(
        "/api/auth/register",
        json={
            "email": "seat-second@example.com",
            "password": "Passw0rd!",
            "display_name": "Seat Second",
        },
    )

    assert second.status_code == 409, second.text
    body = second.json()
    assert body["error"]["code"] == "SEAT_LIMIT_EXCEEDED"
    assert "席位" in body["error"]["message"]

    gen = get_db_session()
    session = next(gen)
    try:
        assert user_repo.get_user_by_email(session, "seat-second@example.com") is None
    finally:
        try:
            next(gen)
        except StopIteration:
            pass
