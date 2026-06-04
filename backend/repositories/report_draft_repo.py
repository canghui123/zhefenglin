"""B3 — Report draft repository.

Every read/write here is tenant-scoped. Status transitions go through
`transition_status`, which enforces the ALLOWED_TRANSITIONS table from
`models.report_draft` and guards against widening distribution unless
the actor is an admin accepting the draft.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.report_draft import ReportDraft
from models.report_draft import (
    ALLOWED_TRANSITIONS,
    DRAFT_ONLY_DISTRIBUTION,
    ReportStatus,
    ReportDistribution,
    ReportTransitionAction,
)


class ReportDraftError(Exception):
    """Domain-level error raised on illegal state transitions / writes."""


# ─────────────────────────────────────────────────────────────────────
# JSON helpers
# ─────────────────────────────────────────────────────────────────────

def _dump(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _load(value: Optional[str]) -> Optional[Any]:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


# ─────────────────────────────────────────────────────────────────────
# Create
# ─────────────────────────────────────────────────────────────────────

def create_draft(
    session: Session,
    *,
    tenant_id: int,
    report_type: str,
    title: str,
    content_json: Optional[dict[str, Any]] = None,
    review_checklist_json: Optional[dict[str, Any]] = None,
    source_context_json: Optional[dict[str, Any]] = None,
    confidence_score: Optional[float] = None,
    agent_run_id: Optional[int] = None,
    related_object_type: Optional[str] = None,
    related_object_id: Optional[str] = None,
    created_by: Optional[int] = None,
) -> ReportDraft:
    """Create a new draft with status='draft', distribution='draft_only'."""
    row = ReportDraft(
        tenant_id=tenant_id,
        agent_run_id=agent_run_id,
        report_type=report_type,
        title=title,
        status="draft",
        distribution=DRAFT_ONLY_DISTRIBUTION,
        content_json=_dump(content_json or {}) or "{}",
        review_checklist_json=_dump(review_checklist_json),
        source_context_json=_dump(source_context_json),
        confidence_score=confidence_score,
        requires_human_review=True,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        created_by=created_by,
    )
    session.add(row)
    session.flush()
    return row


# ─────────────────────────────────────────────────────────────────────
# Read
# ─────────────────────────────────────────────────────────────────────

def get_draft_by_id(
    session: Session, draft_id: int, *, tenant_id: int
) -> Optional[ReportDraft]:
    stmt = (
        select(ReportDraft)
        .where(ReportDraft.id == draft_id)
        .where(ReportDraft.tenant_id == tenant_id)
        .limit(1)
    )
    return session.scalars(stmt).first()


def list_drafts(
    session: Session,
    *,
    tenant_id: int,
    status: Optional[str] = None,
    report_type: Optional[str] = None,
    related_object_type: Optional[str] = None,
    related_object_id: Optional[str] = None,
    limit: int = 100,
) -> List[ReportDraft]:
    stmt = (
        select(ReportDraft)
        .where(ReportDraft.tenant_id == tenant_id)
        .order_by(ReportDraft.id.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(ReportDraft.status == status)
    if report_type:
        stmt = stmt.where(ReportDraft.report_type == report_type)
    if related_object_type:
        stmt = stmt.where(ReportDraft.related_object_type == related_object_type)
    if related_object_id:
        stmt = stmt.where(ReportDraft.related_object_id == related_object_id)
    return list(session.scalars(stmt).all())


# ─────────────────────────────────────────────────────────────────────
# Update (content/title edits, only when status allows)
# ─────────────────────────────────────────────────────────────────────

def update_draft_content(
    session: Session,
    draft: ReportDraft,
    *,
    title: Optional[str] = None,
    content_json: Optional[dict[str, Any]] = None,
    review_checklist_json: Optional[dict[str, Any]] = None,
) -> ReportDraft:
    """Edit draft fields. Only allowed while status is in {draft, needs_revision}.

    Once submitted/accepted/rejected, callers must go through a transition
    (or, for accepted reports, create a follow-up draft).
    """
    if draft.status not in {"draft", "needs_revision"}:
        raise ReportDraftError(
            f"草稿状态为 {draft.status!r},不允许直接编辑内容"
        )
    if title is not None:
        draft.title = title
    if content_json is not None:
        draft.content_json = _dump(content_json) or "{}"
    if review_checklist_json is not None:
        draft.review_checklist_json = _dump(review_checklist_json)
    draft.updated_at = datetime.now(timezone.utc)
    session.flush()
    return draft


# ─────────────────────────────────────────────────────────────────────
# State transitions
# ─────────────────────────────────────────────────────────────────────

_ACTION_TO_TARGET: dict[ReportTransitionAction, ReportStatus] = {
    "submit": "submitted",
    "accept": "accepted",
    "reject": "rejected",
    "request_revision": "needs_revision",
}


def transition_status(
    session: Session,
    draft: ReportDraft,
    *,
    action: ReportTransitionAction,
    actor_id: Optional[int],
    actor_is_admin: bool,
    notes: Optional[str] = None,
    distribution: Optional[ReportDistribution] = None,
) -> ReportDraft:
    """Move draft through the status machine with the audit trail.

    Rules enforced here:
    - target must be reachable per ALLOWED_TRANSITIONS
    - 'accept'/'reject'/'request_revision' require actor_is_admin=True
      (we treat 'accept' as an admin-gated action because it's what
      unlocks distribution widening; reject/needs_revision are also
      admin-only to keep the review trail centred on one role)
    - widening distribution past draft_only requires actor_is_admin=True
      AND the new status to be 'accepted'
    """
    target: ReportStatus = _ACTION_TO_TARGET[action]
    allowed: set[ReportStatus] = ALLOWED_TRANSITIONS[draft.status]  # type: ignore[index]
    if target not in allowed:
        raise ReportDraftError(
            f"非法状态转换: {draft.status} → {target}(action={action})"
        )

    if action in {"accept", "reject", "request_revision"} and not actor_is_admin:
        raise ReportDraftError(
            f"action={action} 需要 admin 权限"
        )

    now = datetime.now(timezone.utc)
    draft.status = target
    if action == "submit":
        draft.submitted_by = actor_id
        draft.submitted_at = now
    if action in {"accept", "reject", "request_revision"}:
        draft.reviewed_by = actor_id
        draft.reviewed_at = now
        if notes:
            draft.review_notes = notes

    # Distribution widening — only when accepting, only by admin
    if distribution is not None:
        if action != "accept":
            raise ReportDraftError(
                "只能在 accept 时同时收窄/放宽 distribution"
            )
        if not actor_is_admin:
            raise ReportDraftError("调整 distribution 需要 admin 权限")
        draft.distribution = distribution
    elif action == "reject":
        # Reset distribution back to draft_only on rejection
        draft.distribution = DRAFT_ONLY_DISTRIBUTION

    draft.updated_at = now
    session.flush()
    return draft


# ─────────────────────────────────────────────────────────────────────
# Serialisation helpers (for API layer)
# ─────────────────────────────────────────────────────────────────────

def serialize_draft(row: ReportDraft) -> dict[str, Any]:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "agent_run_id": row.agent_run_id,
        "report_type": row.report_type,
        "title": row.title,
        "status": row.status,
        "distribution": row.distribution,
        "content_json": _load(row.content_json) or {},
        "review_checklist_json": _load(row.review_checklist_json),
        "source_context_json": _load(row.source_context_json),
        "confidence_score": row.confidence_score,
        "requires_human_review": row.requires_human_review,
        "related_object_type": row.related_object_type,
        "related_object_id": row.related_object_id,
        "created_by": row.created_by,
        "submitted_by": row.submitted_by,
        "submitted_at": row.submitted_at,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at,
        "review_notes": row.review_notes,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def serialize_list_item(row: ReportDraft) -> dict[str, Any]:
    return {
        "id": row.id,
        "report_type": row.report_type,
        "title": row.title,
        "status": row.status,
        "distribution": row.distribution,
        "confidence_score": row.confidence_score,
        "related_object_type": row.related_object_type,
        "related_object_id": row.related_object_id,
        "submitted_at": row.submitted_at,
        "reviewed_at": row.reviewed_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
