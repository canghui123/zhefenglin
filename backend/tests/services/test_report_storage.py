"""Task 7 — report storage integration test.

Simulate → generate report → report_storage_key is populated → download works.
"""
from fastapi.testclient import TestClient

from main import app
from db.session import get_db_session
from repositories import user_repo, tenant_repo, sandbox_repo
from services.password_service import hash_password
from services.storage.factory import get_storage


def _seed_and_login(client: TestClient) -> int:
    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_or_create_tenant(
            session, code="rpt-storage", name="Report Storage"
        )
        user = user_repo.create_user(
            session,
            email="report-storage@example.com",
            password_hash=hash_password("Passw0rd!"),
            role="operator",
            display_name="report-storage",
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
        json={"email": "report-storage@example.com", "password": "Passw0rd!"},
    )
    assert r.status_code == 200
    return uid


def test_report_generation_stores_html_in_storage():
    client = TestClient(app)
    _seed_and_login(client)

    sim = client.post(
        "/api/sandbox/simulate",
        json={
            "car_description": "report storage test",
            "entry_date": "2026-01-15",
            "overdue_amount": 90000,
            "che300_value": 105000,
            "vehicle_type": "japanese",
            "vehicle_age_years": 4,
            "daily_parking": 20,
            "recovery_cost": 1500,
        },
    )
    assert sim.status_code == 200, sim.text
    result_id = sim.json()["id"]

    rpt = client.post(f"/api/sandbox/{result_id}/report")
    assert rpt.status_code == 202

    # DB row should have report_storage_key
    gen = get_db_session()
    session = next(gen)
    try:
        row = sandbox_repo.get_sandbox_result_by_id(
            session, result_id, tenant_id=1
        )
        assert row is not None
        assert row.report_storage_key, "report_storage_key should be set"
        key = row.report_storage_key
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    # Round-trip
    store = get_storage()
    html_bytes = store.get_bytes(key)
    assert b"<html" in html_bytes.lower() or b"<!doctype" in html_bytes.lower()


def test_report_download_endpoint():
    client = TestClient(app)
    _seed_and_login(client)

    sim = client.post(
        "/api/sandbox/simulate",
        json={
            "car_description": "dl report test",
            "entry_date": "2026-02-01",
            "overdue_amount": 80000,
            "che300_value": 95000,
            "vehicle_type": "domestic",
            "vehicle_age_years": 5,
            "daily_parking": 18,
            "recovery_cost": 1200,
        },
    )
    assert sim.status_code == 200
    result_id = sim.json()["id"]

    # Generate
    client.post(f"/api/sandbox/{result_id}/report")

    # Download
    dl = client.get(f"/api/sandbox/{result_id}/report/download")
    assert dl.status_code == 200
    assert "text/html" in dl.headers.get("content-type", "")
