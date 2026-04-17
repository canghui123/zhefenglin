"""Admin APIs for approval requests."""
from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import get_current_user, require_any_role, require_role
from repositories import approval_repo
from services import approval_service, audit_service
from services.tenant_context import get_current_tenant_id


router = APIRouter(prefix="/api/admin/approval-requests", tags=["审批请求"])


class ApprovalCreateRequest(BaseModel):
    type: str
    reason: str
    related_object_type: Optional[str] = None
    related_object_id: Optional[str] = None
    estimated_cost: float = 0
    metadata: Optional[dict[str, Any]] = None


class ApprovalDecisionRequest(BaseModel):
    actual_cost: float = 0


def _json_loads(value: Optional[str]) -> dict:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def _approval_out(row):
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "type": row.type,
        "status": row.status,
        "applicant_user_id": row.applicant_user_id,
        "approver_user_id": row.approver_user_id,
        "reason": row.reason,
        "related_object_type": row.related_object_type,
        "related_object_id": row.related_object_id,
        "estimated_cost": row.estimated_cost,
        "actual_cost": row.actual_cost,
        "metadata": _json_loads(row.metadata_json),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
        "consumed_at": row.consumed_at.isoformat() if row.consumed_at else None,
        "consumed_request_id": row.consumed_request_id,
        "is_consumed": row.consumed_at is not None,
    }


@router.get("")
def list_requests(
    session: Session = Depends(get_db_session),
    user: User = Depends(require_any_role("operator", "manager", "admin")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    rows = (
        approval_repo.list_requests(session)
        if user.role == "admin"
        else approval_repo.list_requests(session, tenant_id=tenant_id)
    )
    return [_approval_out(row) for row in rows]


@router.post("")
def create_request(
    req: ApprovalCreateRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(require_any_role("operator", "manager", "admin")),
    tenant_id: int = Depends(get_current_tenant_id),
):
    row = approval_service.create_request(
        session,
        tenant_id=tenant_id,
        applicant_user_id=user.id,
        type=req.type,
        reason=req.reason,
        related_object_type=req.related_object_type,
        related_object_id=req.related_object_id,
        estimated_cost=req.estimated_cost,
        metadata=req.metadata,
    )
    audit_service.record(
        session,
        request,
        action="approval_create",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="approval_request",
        resource_id=row.id,
        after=req.model_dump(),
    )
    return _approval_out(row)


@router.post("/{approval_request_id}/approve")
def approve_request(
    approval_request_id: int,
    req: ApprovalDecisionRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("admin")),
):
    row = approval_service.approve(
        session,
        approval_request_id=approval_request_id,
        approver_user_id=user.id,
        actual_cost=req.actual_cost,
    )
    audit_service.record(
        session,
        request,
        action="approval_approve",
        tenant_id=row.tenant_id,
        user_id=user.id,
        resource_type="approval_request",
        resource_id=row.id,
        after={"status": row.status, "actual_cost": row.actual_cost},
    )
    return _approval_out(row)


@router.post("/{approval_request_id}/reject")
def reject_request(
    approval_request_id: int,
    req: ApprovalDecisionRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("admin")),
):
    row = approval_service.reject(
        session,
        approval_request_id=approval_request_id,
        approver_user_id=user.id,
        actual_cost=req.actual_cost,
    )
    audit_service.record(
        session,
        request,
        action="approval_reject",
        tenant_id=row.tenant_id,
        user_id=user.id,
        resource_type="approval_request",
        resource_id=row.id,
        after={"status": row.status, "actual_cost": row.actual_cost},
    )
    return _approval_out(row)
