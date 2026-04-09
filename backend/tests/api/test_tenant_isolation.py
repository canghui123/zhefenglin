"""Tenant isolation — Task 6 Step 1.

Two tenants. A user from tenant A must not be able to read or list
resources owned by tenant B, even with a valid session.
"""
import os

from fastapi.testclient import TestClient

from main import app
from db.session import get_db_session
from repositories import user_repo, tenant_repo
from services.password_service import hash_password


SAMPLE_EXCEL = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "sample_asset_package.xlsx"
)


def _seed_tenant_and_user(*, tenant_code: str, email: str, role: str = "operator"):
    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_or_create_tenant(
            session, code=tenant_code, name=tenant_code.upper()
        )
        user = user_repo.create_user(
            session,
            email=email,
            password_hash=hash_password("Passw0rd!"),
            role=role,
            display_name=email,
        )
        tenant_repo.create_membership(session, user_id=user.id, tenant_id=tenant.id)
        user_repo.set_default_tenant(session, user.id, tenant.id)
        session.commit()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def _login(client: TestClient, email: str) -> None:
    r = client.post(
        "/api/auth/login", json={"email": email, "password": "Passw0rd!"}
    )
    assert r.status_code == 200, r.text


def test_user_cannot_read_other_tenant_asset_package():
    _seed_tenant_and_user(tenant_code="alpha", email="alpha@example.com")
    _seed_tenant_and_user(tenant_code="beta", email="beta@example.com")

    # Alpha uploads a package
    alpha = TestClient(app)
    _login(alpha, "alpha@example.com")
    with open(SAMPLE_EXCEL, "rb") as f:
        upload = alpha.post(
            "/api/asset-package/upload",
            files={
                "file": (
                    "alpha.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert upload.status_code == 200, upload.text
    package_id = upload.json()["package_id"]

    # Alpha can read its own package
    own = alpha.get(f"/api/asset-package/{package_id}")
    assert own.status_code == 200

    # Beta cannot read Alpha's package
    beta = TestClient(app)
    _login(beta, "beta@example.com")
    foreign = beta.get(f"/api/asset-package/{package_id}")
    assert foreign.status_code in (403, 404), foreign.text

    # Beta's list does not include Alpha's package
    listed = beta.get("/api/asset-package/list/all")
    assert listed.status_code == 200
    ids = [row["id"] for row in listed.json()]
    assert package_id not in ids


def test_user_cannot_read_other_tenant_sandbox_result():
    _seed_tenant_and_user(tenant_code="alpha", email="alpha@example.com")
    _seed_tenant_and_user(tenant_code="beta", email="beta@example.com")

    alpha = TestClient(app)
    _login(alpha, "alpha@example.com")
    sim = alpha.post(
        "/api/sandbox/simulate",
        json={
            "car_description": "tenant-isolation test",
            "entry_date": "2026-01-01",
            "overdue_amount": 100000,
            "che300_value": 110000,
            "vehicle_type": "japanese",
            "vehicle_age_years": 5,
            "daily_parking": 20,
            "recovery_cost": 1500,
        },
    )
    assert sim.status_code == 200, sim.text
    result_id = sim.json()["id"]

    beta = TestClient(app)
    _login(beta, "beta@example.com")
    foreign = beta.get(f"/api/sandbox/{result_id}")
    assert foreign.status_code in (403, 404)

    listed = beta.get("/api/sandbox/list/all")
    assert listed.status_code == 200
    assert all(r["id"] != result_id for r in listed.json())
