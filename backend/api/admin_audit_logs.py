"""Admin audit log query and export APIs."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import require_role
from repositories import audit_repo
from services.tenant_context import get_current_tenant_id

router = APIRouter(prefix="/api/admin/audit-logs", tags=["审计日志"])


def _serialize(row) -> dict:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "user_id": row.user_id,
        "action": row.action,
        "resource_type": row.resource_type,
        "resource_id": row.resource_id,
        "request_id": row.request_id,
        "ip": row.ip,
        "user_agent": row.user_agent,
        "status": row.status,
        "before_json": row.before_json,
        "after_json": row.after_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("")
def list_audit_logs(
    action: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_role("manager")),
):
    rows = audit_repo.list_logs(session, tenant_id=tenant_id, action=action, limit=limit)
    return [_serialize(row) for row in rows]


@router.get("/export")
def export_audit_logs(
    action: Optional[str] = None,
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_role("manager")),
):
    rows = audit_repo.list_logs(session, tenant_id=tenant_id, action=action, limit=500)
    buffer = io.StringIO()
    buffer.write(
        f"# watermark: tenant={tenant_id}; user={user.id}; exported_at={datetime.utcnow().isoformat()}Z\n"
    )
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "id",
            "tenant_id",
            "user_id",
            "action",
            "resource_type",
            "resource_id",
            "request_id",
            "ip",
            "user_agent",
            "status",
            "created_at",
        ],
    )
    writer.writeheader()
    for row in rows:
        data = _serialize(row)
        writer.writerow({key: data[key] for key in writer.fieldnames})
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit-logs.csv"'},
    )
