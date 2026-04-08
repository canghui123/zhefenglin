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
from repositories import user_repo
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
