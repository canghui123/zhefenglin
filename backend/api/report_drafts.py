"""B3 — Report drafts API.

4 endpoints, tenant-scoped, role-gated, with audit-log writes.

The state machine lives in repositories/report_draft_repo.py; this
module is just the HTTP veneer + auth + audit + error translation.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import require_role
from models.report_draft import (
    ReportDraftListItem,
    ReportDraftOut,
    ReportDraftTransition,
    ReportDraftUpdate,
)
from repositories import report_draft_repo
from repositories.report_draft_repo import ReportDraftError
from services import audit_service
from services import rate_limit_service
from services.tenant_context import get_current_tenant_id
from config import settings


router = APIRouter(prefix="/api/report-drafts", tags=["report-drafts"])


# ─────────────────────────────────────────────────────────────────────
# GET /api/report-drafts — list
# ─────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[ReportDraftListItem])
def list_drafts(
    status_filter: Optional[str] = Query(None, alias="status"),
    report_type: Optional[str] = Query(None),
    related_object_type: Optional[str] = Query(None),
    related_object_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("operator")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    rows = report_draft_repo.list_drafts(
        session,
        tenant_id=tenant_id,
        status=status_filter,
        report_type=report_type,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        limit=limit,
    )
    return [ReportDraftListItem(**report_draft_repo.serialize_list_item(row)) for row in rows]


# ─────────────────────────────────────────────────────────────────────
# GET /api/report-drafts/{id} — detail
# ─────────────────────────────────────────────────────────────────────

@router.get("/{draft_id}", response_model=ReportDraftOut)
def get_draft(
    draft_id: int,
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("operator")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    row = report_draft_repo.get_draft_by_id(session, draft_id, tenant_id=tenant_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="草稿不存在")
    return ReportDraftOut(**report_draft_repo.serialize_draft(row))


# ─────────────────────────────────────────────────────────────────────
# PUT /api/report-drafts/{id} — edit
# ─────────────────────────────────────────────────────────────────────

@router.put("/{draft_id}", response_model=ReportDraftOut)
def update_draft(
    draft_id: int,
    payload: ReportDraftUpdate,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("operator")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    rate_limit_service.enforce_request_limit(
        request,
        scope="report_drafts.update",
        limit=settings.rate_limit_write_max_requests,
    )
    row = report_draft_repo.get_draft_by_id(session, draft_id, tenant_id=tenant_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="草稿不存在")
    try:
        before = report_draft_repo.serialize_list_item(row)
        report_draft_repo.update_draft_content(
            session,
            row,
            title=payload.title,
            content_json=payload.content_json,
            review_checklist_json=payload.review_checklist_json,
        )
        audit_service.record(
            session,
            request,
            action="update",
            tenant_id=tenant_id,
            user_id=user.id,
            resource_type="report_draft",
            resource_id=row.id,
            before=before,
            after=report_draft_repo.serialize_list_item(row),
        )
        session.commit()
    except ReportDraftError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return ReportDraftOut(**report_draft_repo.serialize_draft(row))


# ─────────────────────────────────────────────────────────────────────
# POST /api/report-drafts/{id}/transition — state machine
# ─────────────────────────────────────────────────────────────────────

@router.post("/{draft_id}/transition", response_model=ReportDraftOut)
def transition_draft(
    draft_id: int,
    payload: ReportDraftTransition,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("operator")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    rate_limit_service.enforce_request_limit(
        request,
        scope="report_drafts.transition",
        limit=settings.rate_limit_write_max_requests,
    )
    row = report_draft_repo.get_draft_by_id(session, draft_id, tenant_id=tenant_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="草稿不存在")

    actor_is_admin = (user.role or "").lower() == "admin"
    try:
        before = report_draft_repo.serialize_list_item(row)
        report_draft_repo.transition_status(
            session,
            row,
            action=payload.action,
            actor_id=user.id,
            actor_is_admin=actor_is_admin,
            notes=payload.notes,
            distribution=payload.distribution,
        )
        audit_service.record(
            session,
            request,
            action=f"transition_{payload.action}",
            tenant_id=tenant_id,
            user_id=user.id,
            resource_type="report_draft",
            resource_id=row.id,
            before=before,
            after=report_draft_repo.serialize_list_item(row),
        )
        session.commit()
    except ReportDraftError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return ReportDraftOut(**report_draft_repo.serialize_draft(row))
