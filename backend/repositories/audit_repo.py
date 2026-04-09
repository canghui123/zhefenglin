"""Repository for the audit_logs table.

Every state-changing endpoint records here via `services.audit_service`.
Reads are intentionally minimal — there is no admin UI yet, so listing
helpers are kept to the bare minimum needed by tests.
"""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.audit_log import AuditLog


def create(
    session: Session,
    *,
    tenant_id: Optional[int],
    user_id: Optional[int],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    request_id: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    status: str = "success",
    before_json: Optional[str] = None,
    after_json: Optional[str] = None,
) -> AuditLog:
    row = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id,
        ip=ip,
        user_agent=user_agent,
        status=status,
        before_json=before_json,
        after_json=after_json,
    )
    session.add(row)
    session.flush()
    return row


def list_logs(
    session: Session,
    *,
    tenant_id: Optional[int] = None,
    action: Optional[str] = None,
    limit: int = 100,
) -> List[AuditLog]:
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if tenant_id is not None:
        stmt = stmt.where(AuditLog.tenant_id == tenant_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    return list(session.scalars(stmt).all())
