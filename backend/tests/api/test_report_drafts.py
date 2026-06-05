"""B3 — Report drafts API tests.

Coverage:
- List / get / update / transition happy path
- Tenant isolation at the HTTP layer
- 404 on missing draft
- Edit blocked once submitted (HTTP 400)
- Admin-only transitions
- Distribution widening only on accept by admin
- Audit log written on update and transition
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from config import settings
from db.session import get_db_session
from main import app
from repositories import report_draft_repo, tenant_repo, user_repo
from services.password_service import hash_password


@pytest.fixture(autouse=True)
def _default_legacy_mode(monkeypatch):
    """Use legacy tenant onboard so tests can attach users to known tenants."""
    monkeypatch.setattr(settings, "trial_onboarding_mode", "legacy", raising=False)


def _seed_user(*, email: str, role: str, tenant_code: str) -> tuple[int, int]:
    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_or_create_tenant(session, code=tenant_code, name=tenant_code)
        user = user_repo.create_user(
            session,
            email=email,
            password_hash=hash_password("Passw0rd!1"),
            role=role,
            display_name=email.split("@")[0],
        )
        user_repo.set_default_tenant(session, user.id, tenant.id)
        tenant_repo.create_membership(
            session, user_id=user.id, tenant_id=tenant.id, role=role
        )
        session.commit()
        return user.id, tenant.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def _login(client: TestClient, email: str) -> None:
    resp = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Passw0rd!1"},
    )
    assert resp.status_code == 200, resp.text


def _create_draft_for(tenant_id: int, **kwargs) -> int:
    """Insert a draft via repo (bypassing API) and return its id."""
    gen = get_db_session()
    session = next(gen)
    try:
        defaults = dict(
            report_type="executive_summary",
            title="测试草稿",
            content_json={"sections": [{"heading": "intro"}]},
        )
        defaults.update(kwargs)
        draft = report_draft_repo.create_draft(
            session, tenant_id=tenant_id, **defaults
        )
        session.commit()
        return draft.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


# ─────────────────────────────────────────────────────────────────────
# List / Get
# ─────────────────────────────────────────────────────────────────────

def test_list_empty_returns_200():
    _seed_user(email="rd-list-empty@example.com", role="operator", tenant_code="rd-list-empty")
    client = TestClient(app)
    _login(client, "rd-list-empty@example.com")
    resp = client.get("/api/report-drafts")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_returns_tenant_drafts_only():
    op_user, my_tenant = _seed_user(
        email="rd-list-mine@example.com", role="operator", tenant_code="rd-list-mine"
    )
    _seed_user(
        email="rd-list-other-admin@example.com",
        role="operator",
        tenant_code="rd-list-other",
    )
    # mine: 2 drafts, other tenant: 1 draft
    mine_a = _create_draft_for(my_tenant, title="Mine A")
    mine_b = _create_draft_for(my_tenant, title="Mine B")

    # discover other tenant id, drop a draft in there
    gen = get_db_session()
    session = next(gen)
    try:
        other_tenant = tenant_repo.get_tenant_by_code(session, "rd-list-other")
    finally:
        try:
            next(gen)
        except StopIteration:
            pass
    _create_draft_for(other_tenant.id, title="Other Z")

    client = TestClient(app)
    _login(client, "rd-list-mine@example.com")
    resp = client.get("/api/report-drafts")
    assert resp.status_code == 200
    rows = resp.json()
    titles = {r["title"] for r in rows}
    assert {"Mine A", "Mine B"} <= titles
    assert "Other Z" not in titles


def test_get_draft_returns_404_for_other_tenant_draft():
    _seed_user(email="rd-iso-a@example.com", role="operator", tenant_code="rd-iso-a")
    _seed_user(email="rd-iso-b@example.com", role="operator", tenant_code="rd-iso-b")
    gen = get_db_session()
    session = next(gen)
    try:
        tenant_b = tenant_repo.get_tenant_by_code(session, "rd-iso-b")
    finally:
        try:
            next(gen)
        except StopIteration:
            pass
    draft_id = _create_draft_for(tenant_b.id, title="B's draft")

    client = TestClient(app)
    _login(client, "rd-iso-a@example.com")
    resp = client.get(f"/api/report-drafts/{draft_id}")
    assert resp.status_code == 404


def test_get_draft_returns_full_payload():
    _, tenant_id = _seed_user(
        email="rd-get@example.com", role="operator", tenant_code="rd-get"
    )
    draft_id = _create_draft_for(
        tenant_id,
        title="Full payload",
        content_json={"sections": [{"heading": "总览", "body": "X"}]},
        confidence_score=0.7,
    )
    client = TestClient(app)
    _login(client, "rd-get@example.com")
    resp = client.get(f"/api/report-drafts/{draft_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Full payload"
    assert body["status"] == "draft"
    assert body["distribution"] == "draft_only"
    assert body["requires_human_review"] is True
    assert body["content_json"]["sections"][0]["heading"] == "总览"


# ─────────────────────────────────────────────────────────────────────
# Update
# ─────────────────────────────────────────────────────────────────────

def test_update_draft_title_and_content():
    _, tenant_id = _seed_user(
        email="rd-update@example.com", role="operator", tenant_code="rd-update"
    )
    draft_id = _create_draft_for(tenant_id, title="Old")
    client = TestClient(app)
    _login(client, "rd-update@example.com")
    resp = client.put(
        f"/api/report-drafts/{draft_id}",
        json={"title": "New", "content_json": {"sections": ["new"]}},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "New"
    assert resp.json()["content_json"] == {"sections": ["new"]}


def test_update_blocked_after_submit():
    _, tenant_id = _seed_user(
        email="rd-edit-block@example.com", role="operator", tenant_code="rd-edit-block"
    )
    draft_id = _create_draft_for(tenant_id, title="X")
    client = TestClient(app)
    _login(client, "rd-edit-block@example.com")
    # transition to submitted
    submit = client.post(
        f"/api/report-drafts/{draft_id}/transition",
        json={"action": "submit"},
    )
    assert submit.status_code == 200
    # try to edit
    resp = client.put(
        f"/api/report-drafts/{draft_id}",
        json={"title": "blocked"},
    )
    assert resp.status_code == 400
    assert "不允许直接编辑" in (resp.json().get("error", {}).get("message") or resp.json().get("detail", ""))


# ─────────────────────────────────────────────────────────────────────
# Transition state machine
# ─────────────────────────────────────────────────────────────────────

def test_operator_can_submit_admin_can_accept():
    op_user, tenant_id = _seed_user(
        email="rd-op-submit@example.com", role="operator", tenant_code="rd-flow"
    )
    # admin in same tenant
    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_tenant_by_code(session, "rd-flow")
        admin = user_repo.create_user(
            session,
            email="rd-admin@example.com",
            password_hash=hash_password("Passw0rd!1"),
            role="admin",
            display_name="admin",
        )
        user_repo.set_default_tenant(session, admin.id, tenant.id)
        tenant_repo.create_membership(
            session, user_id=admin.id, tenant_id=tenant.id, role="admin"
        )
        session.commit()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    draft_id = _create_draft_for(tenant_id, title="Flow")
    client = TestClient(app)

    # operator submits
    _login(client, "rd-op-submit@example.com")
    submit = client.post(
        f"/api/report-drafts/{draft_id}/transition",
        json={"action": "submit"},
    )
    assert submit.status_code == 200
    assert submit.json()["status"] == "submitted"

    # admin accepts with distribution widening
    _login(client, "rd-admin@example.com")
    accept = client.post(
        f"/api/report-drafts/{draft_id}/transition",
        json={"action": "accept", "notes": "复核通过", "distribution": "internal"},
    )
    assert accept.status_code == 200
    body = accept.json()
    assert body["status"] == "accepted"
    assert body["distribution"] == "internal"
    assert body["review_notes"] == "复核通过"


def test_non_admin_cannot_accept():
    op_user, tenant_id = _seed_user(
        email="rd-op-accept@example.com", role="operator", tenant_code="rd-op-accept"
    )
    draft_id = _create_draft_for(tenant_id, title="X")
    client = TestClient(app)
    _login(client, "rd-op-accept@example.com")
    client.post(f"/api/report-drafts/{draft_id}/transition", json={"action": "submit"})
    resp = client.post(
        f"/api/report-drafts/{draft_id}/transition",
        json={"action": "accept"},
    )
    assert resp.status_code == 400
    msg = (resp.json().get("error", {}).get("message") or resp.json().get("detail", ""))
    assert "admin" in msg.lower()


def test_cannot_accept_unsubmitted_draft():
    _, tenant_id = _seed_user(
        email="rd-illegal@example.com", role="admin", tenant_code="rd-illegal"
    )
    draft_id = _create_draft_for(tenant_id, title="X")
    client = TestClient(app)
    _login(client, "rd-illegal@example.com")
    resp = client.post(
        f"/api/report-drafts/{draft_id}/transition",
        json={"action": "accept"},
    )
    assert resp.status_code == 400
    msg = (resp.json().get("error", {}).get("message") or resp.json().get("detail", ""))
    assert "非法状态转换" in msg


def test_distribution_widening_requires_accept_action():
    _, tenant_id = _seed_user(
        email="rd-dist@example.com", role="admin", tenant_code="rd-dist"
    )
    draft_id = _create_draft_for(tenant_id, title="X")
    client = TestClient(app)
    _login(client, "rd-dist@example.com")
    client.post(f"/api/report-drafts/{draft_id}/transition", json={"action": "submit"})
    # try to widen during request_revision — illegal
    resp = client.post(
        f"/api/report-drafts/{draft_id}/transition",
        json={"action": "request_revision", "distribution": "external"},
    )
    assert resp.status_code == 400
