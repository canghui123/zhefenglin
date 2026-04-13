"""Task 8 — job lifecycle tests.

The calculate endpoint now returns 202 + job_id. Polling /api/jobs/{id}
returns the status progression: queued → running → succeeded/failed.
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


def _seed_and_login(client: TestClient) -> int:
    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_or_create_tenant(
            session, code="job", name="Job Tenant"
        )
        user = user_repo.create_user(
            session,
            email="job@example.com",
            password_hash=hash_password("Passw0rd!"),
            role="operator",
            display_name="job",
        )
        tenant_repo.create_membership(session, user_id=user.id, tenant_id=tenant.id)
        user_repo.set_default_tenant(session, user.id, tenant.id)
        session.commit()
        return user.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_calculate_returns_202_with_job_id():
    client = TestClient(app)
    _seed_and_login(client)
    r = client.post(
        "/api/auth/login",
        json={"email": "job@example.com", "password": "Passw0rd!"},
    )
    assert r.status_code == 200

    with open(SAMPLE_EXCEL, "rb") as f:
        up = client.post(
            "/api/asset-package/upload",
            files={
                "file": (
                    "job.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert up.status_code == 200
    package_id = up.json()["package_id"]

    calc = client.post(
        "/api/asset-package/calculate",
        json={"package_id": package_id},
    )
    assert calc.status_code == 202, calc.text
    body = calc.json()
    assert "job_id" in body
    job_id = body["job_id"]

    # Poll until succeeded
    status = client.get(f"/api/jobs/{job_id}")
    assert status.status_code == 200
    data = status.json()
    assert data["status"] == "succeeded"
    assert data["result_json"] is not None


def test_job_list_returns_user_jobs():
    client = TestClient(app)
    _seed_and_login(client)
    r = client.post(
        "/api/auth/login",
        json={"email": "job@example.com", "password": "Passw0rd!"},
    )
    assert r.status_code == 200

    with open(SAMPLE_EXCEL, "rb") as f:
        up = client.post(
            "/api/asset-package/upload",
            files={
                "file": (
                    "joblist.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    package_id = up.json()["package_id"]
    client.post("/api/asset-package/calculate", json={"package_id": package_id})

    jobs = client.get("/api/jobs/list")
    assert jobs.status_code == 200
    items = jobs.json()
    assert len(items) >= 1
    assert all("job_type" in j and "status" in j for j in items)
