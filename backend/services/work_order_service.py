"""Execution work order service."""

from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.orm import Session

from db.models.work_order import WorkOrder
from errors import InvalidWorkOrderTransition, WorkOrderNotFound
from models.work_order import WorkOrderCreate, WorkOrderOut
from repositories import work_order_repo


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"in_progress", "completed", "cancelled"},
    "in_progress": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


def _json_loads(value: Optional[str]) -> dict:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def serialize_work_order(row: WorkOrder) -> WorkOrderOut:
    return WorkOrderOut(
        id=row.id,
        tenant_id=row.tenant_id,
        created_by=row.created_by,
        order_type=row.order_type,
        status=row.status,
        priority=row.priority,
        title=row.title,
        target_description=row.target_description,
        source_type=row.source_type,
        source_id=row.source_id,
        payload=_json_loads(row.payload_json),
        result=_json_loads(row.result_json),
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


def create_work_order(
    session: Session,
    *,
    tenant_id: int,
    created_by: Optional[int],
    req: WorkOrderCreate,
) -> WorkOrder:
    payload_json = json.dumps(req.payload, ensure_ascii=False, default=str)
    return work_order_repo.create_work_order(
        session,
        tenant_id=tenant_id,
        created_by=created_by,
        order_type=req.order_type,
        title=req.title,
        priority=req.priority,
        target_description=req.target_description,
        source_type=req.source_type,
        source_id=req.source_id,
        payload_json=payload_json,
    )


def update_work_order_status(
    session: Session,
    *,
    tenant_id: int,
    work_order_id: int,
    status: str,
    result: Optional[dict] = None,
) -> WorkOrder:
    row = work_order_repo.get_work_order_by_id(
        session,
        work_order_id,
        tenant_id=tenant_id,
    )
    if row is None:
        raise WorkOrderNotFound()
    allowed = ALLOWED_TRANSITIONS.get(row.status, set())
    if status != row.status and status not in allowed:
        raise InvalidWorkOrderTransition(f"工单不能从 {row.status} 流转到 {status}")
    row.status = status
    if result is not None:
        row.result_json = json.dumps(result, ensure_ascii=False, default=str)
    session.flush()
    return row
