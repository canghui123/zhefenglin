"""Approval workflow for high-cost operations."""
from __future__ import annotations

import json
from typing import Optional

from errors import (
    ApprovalAlreadyConsumed,
    ApprovalAlreadyDecided,
    ApprovalContextMismatch,
    ApprovalNotApproved,
    ApprovalNotFound,
)
from repositories import approval_repo


def _to_json(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def create_request(
    session,
    *,
    tenant_id: int,
    applicant_user_id: int,
    type: str,
    reason: str,
    related_object_type: Optional[str] = None,
    related_object_id: Optional[str] = None,
    estimated_cost: float = 0,
    metadata=None,
):
    return approval_repo.create_request(
        session,
        tenant_id=tenant_id,
        type=type,
        applicant_user_id=applicant_user_id,
        reason=reason,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        estimated_cost=estimated_cost,
        actual_cost=0,
        metadata_json=_to_json(metadata),
    )


def approve(
    session,
    *,
    approval_request_id: int,
    approver_user_id: int,
    actual_cost: float = 0,
):
    request = approval_repo.get_request_by_id(session, approval_request_id=approval_request_id)
    if request is None:
        raise ApprovalNotFound()
    if request.status != "pending":
        raise ApprovalAlreadyDecided()
    return approval_repo.set_decision(
        session,
        approval_request_id=approval_request_id,
        status="approved",
        approver_user_id=approver_user_id,
        actual_cost=actual_cost,
    )


def reject(
    session,
    *,
    approval_request_id: int,
    approver_user_id: int,
    actual_cost: float = 0,
):
    request = approval_repo.get_request_by_id(session, approval_request_id=approval_request_id)
    if request is None:
        raise ApprovalNotFound()
    if request.status != "pending":
        raise ApprovalAlreadyDecided()
    return approval_repo.set_decision(
        session,
        approval_request_id=approval_request_id,
        status="rejected",
        approver_user_id=approver_user_id,
        actual_cost=actual_cost,
    )


def validate_for_execution(
    session,
    *,
    approval_request_id: int,
    tenant_id: int,
    type: str,
    related_object_type: Optional[str],
    related_object_id: Optional[str],
):
    request = approval_repo.get_request_by_id(session, approval_request_id=approval_request_id)
    if request is None:
        raise ApprovalNotFound()
    if request.tenant_id != tenant_id:
        raise ApprovalContextMismatch()
    if request.status != "approved":
        raise ApprovalNotApproved()
    if request.consumed_at is not None:
        raise ApprovalAlreadyConsumed()
    if request.type != type:
        raise ApprovalContextMismatch()
    if related_object_type is not None and request.related_object_type != related_object_type:
        raise ApprovalContextMismatch()
    if related_object_id is not None and request.related_object_id != related_object_id:
        raise ApprovalContextMismatch()
    return request


def consume_request(
    session,
    *,
    approval_request_id: int,
    consumed_request_id: Optional[str],
):
    request = approval_repo.get_request_by_id(session, approval_request_id=approval_request_id)
    if request is None:
        raise ApprovalNotFound()
    if request.status != "approved":
        raise ApprovalNotApproved()
    if request.consumed_at is not None:
        raise ApprovalAlreadyConsumed()
    return approval_repo.mark_consumed(
        session,
        approval_request_id=approval_request_id,
        consumed_request_id=consumed_request_id,
    )
