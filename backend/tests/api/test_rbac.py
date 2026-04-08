"""RBAC enforcement — Task 5 Step 1.

Contract:
- A `viewer` user cannot reach manager-only endpoints (`/api/portfolio/manager-playbook`).
- A `manager` user can.
- All previously-public business endpoints now require authentication.
"""
from fastapi.testclient import TestClient

from main import app
from db.session import get_db_session
from repositories import user_repo
from services.password_service import hash_password


def _seed(email, role, password="Passw0rd!"):
    gen = get_db_session()
    session = next(gen)
    try:
        user_repo.create_user(
            session,
            email=email,
            password_hash=hash_password(password),
            role=role,
            display_name=role,
        )
        session.commit()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def _login(client: TestClient, email: str, password: str = "Passw0rd!"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_unauthenticated_request_to_protected_endpoint_returns_401():
    client = TestClient(app)
    response = client.get("/api/portfolio/overview")
    assert response.status_code == 401


def test_viewer_cannot_call_manager_only_endpoint():
    _seed("viewer@example.com", "viewer")
    _seed("manager@example.com", "manager")

    client = TestClient(app)
    _login(client, "viewer@example.com")

    response = client.get("/api/portfolio/manager-playbook")
    assert response.status_code == 403


def test_manager_can_call_manager_only_endpoint():
    _seed("manager@example.com", "manager")

    client = TestClient(app)
    _login(client, "manager@example.com")

    response = client.get("/api/portfolio/manager-playbook")
    assert response.status_code == 200


def test_health_endpoint_remains_public():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
