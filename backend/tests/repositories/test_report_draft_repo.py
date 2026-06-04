"""B3 — Report draft repository tests.

Coverage:
- CRUD basics
- Status machine: legal & illegal transitions
- Admin-only transitions (accept/reject/request_revision)
- Distribution gated to draft_only unless admin accepts
- Tenant isolation
- Edit blocked after submission
- JSON dump/load round-trip
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from db.session import get_db_session
from repositories import report_draft_repo, tenant_repo
from repositories.report_draft_repo import ReportDraftError


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _get_session() -> tuple[Session, object]:
    gen = get_db_session()
    return next(gen), gen


def _close_session(gen) -> None:
    try:
        next(gen)
    except StopIteration:
        pass


def _seed_tenant(session: Session, code: str, name: str):
    return tenant_repo.get_or_create_tenant(session, code=code, name=name)


@pytest.fixture
def session_and_tenant():
    session, gen = _get_session()
    tenant = _seed_tenant(session, code="rdrep_test_t1", name="Report Test Tenant 1")
    session.commit()
    yield session, tenant
    _close_session(gen)


# ─────────────────────────────────────────────────────────────────────
# Create + Read
# ─────────────────────────────────────────────────────────────────────

def test_create_draft_sets_initial_status_and_distribution(session_and_tenant):
    session, tenant = session_and_tenant
    draft = report_draft_repo.create_draft(
        session,
        tenant_id=tenant.id,
        report_type="executive_summary",
        title="周度高管摘要",
        content_json={"sections": [{"heading": "总览"}]},
        confidence_score=0.78,
    )
    session.commit()

    assert draft.id is not None
    assert draft.status == "draft"
    assert draft.distribution == "draft_only"
    assert draft.requires_human_review is True
    assert draft.report_type == "executive_summary"


def test_get_and_list_drafts_by_tenant(session_and_tenant):
    session, tenant = session_and_tenant
    a = report_draft_repo.create_draft(
        session, tenant_id=tenant.id, report_type="executive_summary", title="A"
    )
    b = report_draft_repo.create_draft(
        session, tenant_id=tenant.id, report_type="buyer_offer_memo", title="B"
    )
    session.commit()

    got = report_draft_repo.get_draft_by_id(session, a.id, tenant_id=tenant.id)
    assert got is not None
    assert got.title == "A"

    all_drafts = report_draft_repo.list_drafts(session, tenant_id=tenant.id)
    titles = {d.title for d in all_drafts}
    assert {"A", "B"} <= titles


def test_list_drafts_filters_status(session_and_tenant):
    session, tenant = session_and_tenant
    a = report_draft_repo.create_draft(
        session, tenant_id=tenant.id, report_type="executive_summary", title="A"
    )
    b = report_draft_repo.create_draft(
        session, tenant_id=tenant.id, report_type="executive_summary", title="B"
    )
    session.commit()
    report_draft_repo.transition_status(
        session, a, action="submit", actor_id=1, actor_is_admin=False
    )
    session.commit()

    submitted = report_draft_repo.list_drafts(session, tenant_id=tenant.id, status="submitted")
    assert a.id in {d.id for d in submitted}
    assert b.id not in {d.id for d in submitted}


# ─────────────────────────────────────────────────────────────────────
# Tenant isolation
# ─────────────────────────────────────────────────────────────────────

def test_drafts_scoped_to_tenant(session_and_tenant):
    session, tenant = session_and_tenant
    other = _seed_tenant(session, code="rdrep_test_t2", name="Other Tenant")
    a = report_draft_repo.create_draft(
        session, tenant_id=tenant.id, report_type="executive_summary", title="A-mine"
    )
    b = report_draft_repo.create_draft(
        session, tenant_id=other.id, report_type="executive_summary", title="B-other"
    )
    session.commit()

    # Other tenant cannot read mine
    assert report_draft_repo.get_draft_by_id(session, a.id, tenant_id=other.id) is None
    # And I cannot read other
    assert report_draft_repo.get_draft_by_id(session, b.id, tenant_id=tenant.id) is None


# ─────────────────────────────────────────────────────────────────────
# State machine — legal transitions
# ─────────────────────────────────────────────────────────────────────

def test_submit_then_accept_flow(session_and_tenant):
    session, tenant = session_and_tenant
    draft = report_draft_repo.create_draft(
        session, tenant_id=tenant.id, report_type="executive_summary", title="X"
    )
    session.commit()

    # operator submits
    report_draft_repo.transition_status(
        session, draft, action="submit", actor_id=10, actor_is_admin=False
    )
    assert draft.status == "submitted"
    assert draft.submitted_by == 10
    assert draft.submitted_at is not None

    # admin accepts
    report_draft_repo.transition_status(
        session,
        draft,
        action="accept",
        actor_id=20,
        actor_is_admin=True,
        notes="复核通过",
        distribution="internal",
    )
    assert draft.status == "accepted"
    assert draft.distribution == "internal"
    assert draft.reviewed_by == 20
    assert draft.reviewed_at is not None
    assert draft.review_notes == "复核通过"


def test_request_revision_returns_to_needs_revision_and_resubmits(session_and_tenant):
    session, tenant = session_and_tenant
    draft = report_draft_repo.create_draft(
        session, tenant_id=tenant.id, report_type="executive_summary", title="X"
    )
    report_draft_repo.transition_status(
        session, draft, action="submit", actor_id=10, actor_is_admin=False
    )
    report_draft_repo.transition_status(
        session,
        draft,
        action="request_revision",
        actor_id=20,
        actor_is_admin=True,
        notes="补充市场数据",
    )
    assert draft.status == "needs_revision"
    # 可以重新 submit
    report_draft_repo.transition_status(
        session, draft, action="submit", actor_id=10, actor_is_admin=False
    )
    assert draft.status == "submitted"


def test_reject_resets_distribution_to_draft_only(session_and_tenant):
    session, tenant = session_and_tenant
    draft = report_draft_repo.create_draft(
        session, tenant_id=tenant.id, report_type="executive_summary", title="X"
    )
    report_draft_repo.transition_status(
        session, draft, action="submit", actor_id=10, actor_is_admin=False
    )
    report_draft_repo.transition_status(
        session, draft, action="reject", actor_id=20, actor_is_admin=True, notes="资料不足"
    )
    assert draft.status == "rejected"
    assert draft.distribution == "draft_only"


# ─────────────────────────────────────────────────────────────────────
# State machine — illegal transitions
# ─────────────────────────────────────────────────────────────────────

def test_cannot_accept_a_draft_that_was_not_submitted(session_and_tenant):
    session, tenant = session_and_tenant
    draft = report_draft_repo.create_draft(
        session, tenant_id=tenant.id, report_type="executive_summary", title="X"
    )
    with pytest.raises(ReportDraftError) as exc:
        report_draft_repo.transition_status(
            session, draft, action="accept", actor_id=20, actor_is_admin=True
        )
    assert "非法状态转换" in str(exc.value)


def test_cannot_resubmit_an_accepted_draft(session_and_tenant):
    session, tenant = session_and_tenant
    draft = report_draft_repo.create_draft(
        session, tenant_id=tenant.id, report_type="executive_summary", title="X"
    )
    report_draft_repo.transition_status(
        session, draft, action="submit", actor_id=10, actor_is_admin=False
    )
    report_draft_repo.transition_status(
        session, draft, action="accept", actor_id=20, actor_is_admin=True
    )
    with pytest.raises(ReportDraftError):
        report_draft_repo.transition_status(
            session, draft, action="submit", actor_id=10, actor_is_admin=False
        )


# ─────────────────────────────────────────────────────────────────────
# Admin-gated transitions
# ─────────────────────────────────────────────────────────────────────

def test_non_admin_cannot_accept(session_and_tenant):
    session, tenant = session_and_tenant
    draft = report_draft_repo.create_draft(
        session, tenant_id=tenant.id, report_type="executive_summary", title="X"
    )
    report_draft_repo.transition_status(
        session, draft, action="submit", actor_id=10, actor_is_admin=False
    )
    with pytest.raises(ReportDraftError) as exc:
        report_draft_repo.transition_status(
            session, draft, action="accept", actor_id=11, actor_is_admin=False
        )
    assert "admin 权限" in str(exc.value)


def test_non_admin_cannot_reject(session_and_tenant):
    session, tenant = session_and_tenant
    draft = report_draft_repo.create_draft(
        session, tenant_id=tenant.id, report_type="executive_summary", title="X"
    )
    report_draft_repo.transition_status(
        session, draft, action="submit", actor_id=10, actor_is_admin=False
    )
    with pytest.raises(ReportDraftError):
        report_draft_repo.transition_status(
            session, draft, action="reject", actor_id=11, actor_is_admin=False
        )


def test_non_admin_cannot_request_revision(session_and_tenant):
    session, tenant = session_and_tenant
    draft = report_draft_repo.create_draft(
        session, tenant_id=tenant.id, report_type="executive_summary", title="X"
    )
    report_draft_repo.transition_status(
        session, draft, action="submit", actor_id=10, actor_is_admin=False
    )
    with pytest.raises(ReportDraftError):
        report_draft_repo.transition_status(
            session, draft, action="request_revision", actor_id=11, actor_is_admin=False
        )


# ─────────────────────────────────────────────────────────────────────
# Distribution gating
# ─────────────────────────────────────────────────────────────────────

def test_widening_distribution_requires_accept_action(session_and_tenant):
    session, tenant = session_and_tenant
    draft = report_draft_repo.create_draft(
        session, tenant_id=tenant.id, report_type="executive_summary", title="X"
    )
    report_draft_repo.transition_status(
        session, draft, action="submit", actor_id=10, actor_is_admin=False
    )
    # try to set distribution while requesting revision — illegal
    with pytest.raises(ReportDraftError) as exc:
        report_draft_repo.transition_status(
            session,
            draft,
            action="request_revision",
            actor_id=20,
            actor_is_admin=True,
            distribution="external",
        )
    assert "distribution" in str(exc.value)


def test_distribution_widening_requires_admin(session_and_tenant):
    # Non-admin cannot even reach this branch because accept requires admin,
    # but explicitly assert what the error looks like.
    session, tenant = session_and_tenant
    draft = report_draft_repo.create_draft(
        session, tenant_id=tenant.id, report_type="executive_summary", title="X"
    )
    report_draft_repo.transition_status(
        session, draft, action="submit", actor_id=10, actor_is_admin=False
    )
    with pytest.raises(ReportDraftError):
        report_draft_repo.transition_status(
            session,
            draft,
            action="accept",
            actor_id=11,
            actor_is_admin=False,  # not admin
            distribution="external",
        )


# ─────────────────────────────────────────────────────────────────────
# Editing
# ─────────────────────────────────────────────────────────────────────

def test_update_draft_content_only_in_editable_states(session_and_tenant):
    session, tenant = session_and_tenant
    draft = report_draft_repo.create_draft(
        session, tenant_id=tenant.id, report_type="executive_summary", title="X"
    )
    # draft → editable
    report_draft_repo.update_draft_content(
        session, draft, title="X-edited", content_json={"sections": ["new"]}
    )
    assert draft.title == "X-edited"

    # submit → not editable
    report_draft_repo.transition_status(
        session, draft, action="submit", actor_id=10, actor_is_admin=False
    )
    with pytest.raises(ReportDraftError) as exc:
        report_draft_repo.update_draft_content(session, draft, title="X-blocked")
    assert "不允许直接编辑" in str(exc.value)

    # needs_revision → editable again
    report_draft_repo.transition_status(
        session, draft, action="request_revision", actor_id=20, actor_is_admin=True
    )
    report_draft_repo.update_draft_content(session, draft, title="X-revised")
    assert draft.title == "X-revised"


# ─────────────────────────────────────────────────────────────────────
# JSON round-trip
# ─────────────────────────────────────────────────────────────────────

def test_content_json_round_trip(session_and_tenant):
    session, tenant = session_and_tenant
    content = {
        "sections": [
            {"heading": "总览", "body": "30 台车 / M12+ 19 台"},
            {"heading": "建议动作", "body": "优先法务推进"},
        ],
        "evidence_refs": ["agent_run_42"],
    }
    draft = report_draft_repo.create_draft(
        session,
        tenant_id=tenant.id,
        report_type="executive_summary",
        title="Round-trip",
        content_json=content,
    )
    session.commit()

    serialized = report_draft_repo.serialize_draft(draft)
    assert serialized["content_json"] == content
