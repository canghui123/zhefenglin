"""B6/2 — Cross-tenant isolation for SaaS trial endpoints.

The existing test_tenant_isolation.py covers asset_packages and sandbox.
Once we open public trial signup, every endpoint that takes a resource
ID needs the same audit. This file fills the gaps:

- /api/tasks/{id}                          work_orders
- /api/ai-command-center/runs/{id}        agent_runs (most impactful —
                                          may contain rich Agent output
                                          including business sensitive data)
- /api/ai-command-center/decision-audit-logs  list view
- /api/report-drafts/{id}                  B3 — already in test_report_drafts
                                           but a list-view negative test is
                                           still worth having here
- /api/tasks (list)                        work_orders list shouldn't
                                           surface other-tenant rows

Pattern in all tests: two tenants A and B, A creates a resource, B logs
in and tries to read / write — expect 403 or 404, never 200.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from config import settings
from db.session import get_db_session
from main import app
from repositories import (
    agent_repo,
    report_draft_repo,
    tenant_repo,
    user_repo,
    work_order_repo,
)
from services.password_service import hash_password


def _seed_tenant_user(*, tenant_code: str, email: str, role: str = "operator"):
    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_or_create_tenant(
            session, code=tenant_code, name=tenant_code.upper()
        )
        user = user_repo.create_user(
            session,
            email=email,
            password_hash=hash_password("Passw0rd!1"),
            role=role,
            display_name=email,
        )
        tenant_repo.create_membership(session, user_id=user.id, tenant_id=tenant.id, role=role)
        user_repo.set_default_tenant(session, user.id, tenant.id)
        session.commit()
        return user.id, tenant.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def _login(client: TestClient, email: str) -> None:
    r = client.post("/api/auth/login", json={"email": email, "password": "Passw0rd!1"})
    assert r.status_code == 200, r.text


import pytest


@pytest.fixture(autouse=True)
def _legacy_mode(monkeypatch):
    """Pin trial onboarding to legacy so tests can use deterministic tenant codes."""
    monkeypatch.setattr(settings, "trial_onboarding_mode", "legacy", raising=False)


# ─────────────────────────────────────────────────────────────────────
# /api/report-drafts list — must not surface other-tenant rows
# ─────────────────────────────────────────────────────────────────────

def test_report_drafts_list_excludes_other_tenant_rows():
    a_user, a_tenant = _seed_tenant_user(
        tenant_code="iso-rd-a", email="iso-rd-a@example.com"
    )
    b_user, b_tenant = _seed_tenant_user(
        tenant_code="iso-rd-b", email="iso-rd-b@example.com"
    )

    gen = get_db_session()
    session = next(gen)
    try:
        a_draft = report_draft_repo.create_draft(
            session,
            tenant_id=a_tenant,
            report_type="executive_summary",
            title="A 的草稿(机密)",
            content_json={"sections": [{"heading": "intro"}]},
        )
        session.commit()
        a_draft_id = a_draft.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    client = TestClient(app)
    _login(client, "iso-rd-b@example.com")

    resp = client.get("/api/report-drafts")
    assert resp.status_code == 200
    titles = {row["title"] for row in resp.json()}
    assert "A 的草稿(机密)" not in titles

    # Direct fetch of A's draft from B's session → 404
    resp2 = client.get(f"/api/report-drafts/{a_draft_id}")
    assert resp2.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# /api/report-drafts/{id}/transition — write-side isolation
# ─────────────────────────────────────────────────────────────────────

def test_report_drafts_transition_blocked_cross_tenant():
    a_user, a_tenant = _seed_tenant_user(
        tenant_code="iso-rd-w-a", email="iso-rd-w-a@example.com"
    )
    b_user, b_tenant = _seed_tenant_user(
        tenant_code="iso-rd-w-b", email="iso-rd-w-b@example.com", role="admin"
    )

    gen = get_db_session()
    session = next(gen)
    try:
        a_draft = report_draft_repo.create_draft(
            session,
            tenant_id=a_tenant,
            report_type="executive_summary",
            title="X",
        )
        # Pre-submit as A so B has something to "accept"
        report_draft_repo.transition_status(
            session, a_draft, action="submit", actor_id=a_user, actor_is_admin=False
        )
        session.commit()
        a_draft_id = a_draft.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    client = TestClient(app)
    _login(client, "iso-rd-w-b@example.com")
    # B (admin in their own tenant) tries to accept A's draft → 404
    resp = client.post(
        f"/api/report-drafts/{a_draft_id}/transition",
        json={"action": "accept", "notes": "试图越权"},
    )
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# /api/tasks list and detail — work_orders
# ─────────────────────────────────────────────────────────────────────

def test_tasks_list_excludes_other_tenant_work_orders():
    a_user, a_tenant = _seed_tenant_user(
        tenant_code="iso-tasks-a", email="iso-tasks-a@example.com"
    )
    b_user, b_tenant = _seed_tenant_user(
        tenant_code="iso-tasks-b", email="iso-tasks-b@example.com"
    )

    gen = get_db_session()
    session = next(gen)
    try:
        # Plant a work_order owned by A
        a_wo = work_order_repo.create_work_order(
            session,
            tenant_id=a_tenant,
            created_by=a_user,
            order_type="towing",
            title="A 的拖车任务(机密)",
            priority="medium",
        )
        session.commit()
        a_wo_id = a_wo.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    client = TestClient(app)
    _login(client, "iso-tasks-b@example.com")

    resp = client.get("/api/tasks")
    assert resp.status_code == 200
    rows = resp.json()
    titles = {row.get("title") for row in rows}
    assert "A 的拖车任务(机密)" not in titles
    # detail
    resp2 = client.get(f"/api/tasks/{a_wo_id}")
    assert resp2.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# /api/ai-command-center/runs/{id} — agent_runs
# ─────────────────────────────────────────────────────────────────────

def test_agent_run_detail_blocked_cross_tenant():
    a_user, a_tenant = _seed_tenant_user(
        tenant_code="iso-ar-a", email="iso-ar-a@example.com"
    )
    b_user, b_tenant = _seed_tenant_user(
        tenant_code="iso-ar-b", email="iso-ar-b@example.com"
    )

    gen = get_db_session()
    session = next(gen)
    try:
        # Insert an agent run owned by A
        from db.models.agent import AgentRun

        a_run = AgentRun(
            tenant_id=a_tenant,
            agent_type="asset_package_diagnosis_agent",
            input_json=json.dumps({"x": 1}, ensure_ascii=False),
            output_json=json.dumps({"summary": "A 的机密 Agent 输出"}, ensure_ascii=False),
            status="completed",
            created_by=a_user,
        )
        session.add(a_run)
        session.commit()
        a_run_id = a_run.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    client = TestClient(app)
    _login(client, "iso-ar-b@example.com")

    # GET /api/ai-command-center/runs/{id} → must 404
    resp = client.get(f"/api/ai-command-center/runs/{a_run_id}")
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────
# /api/ai-command-center/decision-audit-logs list
# ─────────────────────────────────────────────────────────────────────

def test_decision_audit_logs_list_isolated():
    """admin in B can list their own audit logs but not A's."""
    a_user, a_tenant = _seed_tenant_user(
        tenant_code="iso-dal-a", email="iso-dal-a@example.com", role="admin"
    )
    b_user, b_tenant = _seed_tenant_user(
        tenant_code="iso-dal-b", email="iso-dal-b@example.com", role="admin"
    )

    gen = get_db_session()
    session = next(gen)
    try:
        agent_repo.create_decision_audit_log(
            session,
            tenant_id=a_tenant,
            agent_run_id=None,
            decision_type="report_review",
            action="accept",
            actor_user_id=a_user,
            before=None,
            after={"summary": "A 的机密审计 / 含 VIN LSVCD23F4N1234567"},
            requires_human_review=True,
        )
        session.commit()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    client = TestClient(app)
    _login(client, "iso-dal-b@example.com")

    resp = client.get("/api/ai-command-center/decision-audit-logs")
    assert resp.status_code == 200
    rows = resp.json()
    # B 的审计日志列表里不该出现 A 的记录
    for row in rows:
        after = row.get("after") or {}
        summary = after.get("summary") or ""
        assert "A 的机密" not in summary
        # 即使 leaked, PII 也必须脱敏
        assert "LSVCD23F4N1234567" not in summary
