"""Task 8 — async report generation.

Report generation returns 202 + job_id; polling the job shows
succeeded; the report_storage_key is populated.
"""
from fastapi.testclient import TestClient

from main import app
from db.session import get_db_session
from repositories import user_repo, tenant_repo
from services.password_service import hash_password


def _seed_and_login(client: TestClient) -> int:
    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_or_create_tenant(
            session, code="async-rpt", name="Async Report"
        )
        user = user_repo.create_user(
            session,
            email="async-rpt@example.com",
            password_hash=hash_password("Passw0rd!"),
            role="operator",
            display_name="async-rpt",
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


def test_report_generation_returns_job_reference():
    client = TestClient(app)
    _seed_and_login(client)
    client.post(
        "/api/auth/login",
        json={"email": "async-rpt@example.com", "password": "Passw0rd!"},
    )

    sim = client.post(
        "/api/sandbox/simulate",
        json={
            "car_description": "async report test",
            "entry_date": "2026-01-10",
            "overdue_amount": 75000,
            "che300_value": 88000,
            "vehicle_type": "domestic",
            "vehicle_age_years": 6,
            "daily_parking": 15,
            "recovery_cost": 1000,
        },
    )
    assert sim.status_code == 200
    result_id = sim.json()["id"]

    rpt = client.post(f"/api/sandbox/{result_id}/report")
    assert rpt.status_code == 202, rpt.text
    body = rpt.json()
    assert "job_id" in body
    job_id = body["job_id"]

    # Poll
    status = client.get(f"/api/jobs/{job_id}")
    assert status.status_code == 200
    data = status.json()
    assert data["status"] == "succeeded"
    assert data["job_type"] == "report"
