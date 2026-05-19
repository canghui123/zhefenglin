"""Repository helpers for disposal work orders."""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.work_order import WorkOrder


def _dump(value: Optional[dict[str, Any]]) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def create_work_order(
    session: Session,
    *,
    tenant_id: int,
    created_by: Optional[int],
    order_type: str,
    title: str,
    priority: str = "normal",
    status: str = "pending",
    target_description: Optional[str] = None,
    source_type: Optional[str] = None,
    source_id: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
    result: Optional[dict[str, Any]] = None,
) -> WorkOrder:
    row = WorkOrder(
        tenant_id=tenant_id,
        created_by=created_by,
        order_type=order_type,
        status=status,
        priority=priority,
        title=title,
        target_description=target_description,
        source_type=source_type,
        source_id=source_id,
        payload_json=_dump(payload),
        result_json=_dump(result),
    )
    session.add(row)
    session.flush()
    return row


def get_work_order(
    session: Session,
    work_order_id: int,
    *,
    tenant_id: int,
) -> Optional[WorkOrder]:
    stmt = (
        select(WorkOrder)
        .where(WorkOrder.id == work_order_id)
        .where(WorkOrder.tenant_id == tenant_id)
        .limit(1)
    )
    return session.scalars(stmt).first()


def list_work_orders(
    session: Session,
    *,
    tenant_id: int,
    status: Optional[str] = None,
    order_type: Optional[str] = None,
    limit: int = 100,
) -> list[WorkOrder]:
    stmt = (
        select(WorkOrder)
        .where(WorkOrder.tenant_id == tenant_id)
        .order_by(WorkOrder.updated_at.desc(), WorkOrder.id.desc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(WorkOrder.status == status)
    if order_type:
        stmt = stmt.where(WorkOrder.order_type == order_type)
    return list(session.scalars(stmt).all())


def list_work_orders_for_tenant(session: Session, *, tenant_id: int) -> list[WorkOrder]:
    stmt = (
        select(WorkOrder)
        .where(WorkOrder.tenant_id == tenant_id)
        .order_by(WorkOrder.updated_at.desc(), WorkOrder.id.desc())
    )
    return list(session.scalars(stmt).all())


def find_open_by_source(
    session: Session,
    *,
    tenant_id: int,
    source_type: str,
    source_id: str,
    order_type: str,
) -> Optional[WorkOrder]:
    stmt = (
        select(WorkOrder)
        .where(WorkOrder.tenant_id == tenant_id)
        .where(WorkOrder.source_type == source_type)
        .where(WorkOrder.source_id == source_id)
        .where(WorkOrder.order_type == order_type)
        .where(WorkOrder.status.in_(["pending", "assigned", "in_progress", "blocked"]))
        .order_by(WorkOrder.id.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def update_work_order(
    row: WorkOrder,
    *,
    order_type: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    title: Optional[str] = None,
    target_description: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
    result: Optional[dict[str, Any]] = None,
) -> WorkOrder:
    if order_type is not None:
        row.order_type = order_type
    if status is not None:
        row.status = status
    if priority is not None:
        row.priority = priority
    if title is not None:
        row.title = title
    if target_description is not None:
        row.target_description = target_description
    if payload is not None:
        row.payload_json = _dump(payload)
    if result is not None:
        row.result_json = _dump(result)
    return row
