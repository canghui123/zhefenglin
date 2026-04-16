"""Repository for approval requests."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.valuation_control import ApprovalRequest


def create_request(
    session: Session,
    *,
    tenant_id: int,
    type: str,
    applicant_user_id: int,
    reason: str,
    related_object_type: Optional[str] = None,
    related_object_id: Optional[str] = None,
    estimated_cost: float = 0,
    actual_cost: float = 0,
    metadata_json: Optional[str] = None,
) -> ApprovalRequest:
    row = ApprovalRequest(
        tenant_id=tenant_id,
        type=type,
        applicant_user_id=applicant_user_id,
        reason=reason,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        estimated_cost=estimated_cost,
        actual_cost=actual_cost,
        metadata_json=metadata_json,
    )
    session.add(row)
    session.flush()
    return row


def get_request_by_id(
    session: Session, *, approval_request_id: int
) -> Optional[ApprovalRequest]:
    return session.get(ApprovalRequest, approval_request_id)


def list_requests(session: Session, *, tenant_id: Optional[int] = None) -> List[ApprovalRequest]:
    stmt = select(ApprovalRequest).order_by(ApprovalRequest.id.desc())
    if tenant_id is not None:
        stmt = stmt.where(ApprovalRequest.tenant_id == tenant_id)
    return list(session.scalars(stmt).all())


def set_decision(
    session: Session,
    *,
    approval_request_id: int,
    status: str,
    approver_user_id: int,
    actual_cost: float,
) -> Optional[ApprovalRequest]:
    row = get_request_by_id(session, approval_request_id=approval_request_id)
    if row is None:
        return None
    row.status = status
    row.approver_user_id = approver_user_id
    row.actual_cost = actual_cost
    row.decided_at = datetime.utcnow()
    session.flush()
    return row
