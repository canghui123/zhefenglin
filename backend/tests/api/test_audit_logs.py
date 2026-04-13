"""Audit log coverage — Task 6 Step 1.

Every state-changing endpoint (login, upload, calculate, simulate,
generate report) must persist an `audit_logs` row with at least:
tenant_id, user_id, action, resource_type, resource_id, request_id,
ip, user_agent. The repo-layer test uses the ORM model directly so a
regression there fails loudly.
"""
import os
from typing import List, Optional

from fastapi.testclient import TestClient
from sqlalchemy import select

from main import app
from db.session import get_db_session
from db.models.audit_log import AuditLog
from repositories import user_repo, tenant_repo
from services.password_service import hash_password


SAMPLE_EXCEL = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "sample_asset_package.xlsx"
)


def _seed_user_with_tenant(email: str, role: str = "operator") -> int:
    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_or_create_tenant(
            session, code="audit", name="Audit Tenant"
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
        return user.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def _read_audit_logs(action: Optional[str] = None) -> List[AuditLog]:
    gen = get_db_session()
    session = next(gen)
    try:
        stmt = select(AuditLog).order_by(AuditLog.id)
        if action is not None:
            stmt = stmt.where(AuditLog.action == action)
        return list(session.scalars(stmt).all())
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_login_writes_audit_log():
    user_id = _seed_user_with_tenant("audit-login@example.com")

    client = TestClient(app)
    r = client.post(
        "/api/auth/login",
        json={"email": "audit-login@example.com", "password": "Passw0rd!"},
        headers={"User-Agent": "pytest-ua/1.0"},
    )
    assert r.status_code == 200, r.text

    rows = _read_audit_logs(action="login")
    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == user_id
    assert row.tenant_id is not None
    assert row.resource_type == "user"
    assert row.resource_id == str(user_id)
    assert row.request_id  # populated by middleware
    assert row.user_agent == "pytest-ua/1.0"


def test_upload_calculate_simulate_report_write_audit_logs():
    user_id = _seed_user_with_tenant("audit-flow@example.com")

    client = TestClient(app)
    client.headers.update({"User-Agent": "pytest-flow/1.0"})
    login = client.post(
        "/api/auth/login",
        json={"email": "audit-flow@example.com", "password": "Passw0rd!"},
    )
    assert login.status_code == 200, login.text

    # Upload
    with open(SAMPLE_EXCEL, "rb") as f:
        up = client.post(
            "/api/asset-package/upload",
            files={
                "file": (
                    "audit.xlsx",
                    f,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    assert up.status_code == 200, up.text
    package_id = up.json()["package_id"]

    # Calculate
    calc = client.post(
        "/api/asset-package/calculate",
        json={"package_id": package_id},
    )
    assert calc.status_code == 202, calc.text

    # Simulate
    sim = client.post(
        "/api/sandbox/simulate",
        json={
            "car_description": "audit flow test",
            "entry_date": "2026-02-01",
            "overdue_amount": 80000,
            "che300_value": 95000,
            "vehicle_type": "japanese",
            "vehicle_age_years": 4,
            "daily_parking": 18,
            "recovery_cost": 1500,
        },
    )
    assert sim.status_code == 200, sim.text
    result_id = sim.json()["id"]

    # Report
    report = client.post(f"/api/sandbox/{result_id}/report")
    assert report.status_code == 202

    actions = {row.action for row in _read_audit_logs()}
    assert {"login", "upload", "calculate", "simulate", "report"} <= actions

    upload_rows = _read_audit_logs(action="upload")
    assert any(
        r.user_id == user_id
        and r.resource_type == "asset_package"
        and r.resource_id == str(package_id)
        and r.user_agent == "pytest-flow/1.0"
        and r.request_id
        for r in upload_rows
    )

    sim_rows = _read_audit_logs(action="simulate")
    assert any(
        r.resource_type == "sandbox_result" and r.resource_id == str(result_id)
        for r in sim_rows
    )
