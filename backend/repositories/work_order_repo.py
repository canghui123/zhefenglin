"""Repository for tenant-scoped execution work orders."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.work_order import WorkOrder


def create_work_order(
    session: Session,
    *,
    tenant_id: int,
    created_by: Optional[int],
    order_type: str,
    title: str,
    priority: str,
    target_description: Optional[str],
    source_type: Optional[str],
    source_id: Optional[str],
    payload_json: str,
) -> WorkOrder:
    row = WorkOrder(
        tenant_id=tenant_id,
        created_by=created_by,
        order_type=order_type,
        title=title,
        priority=priority,
        target_description=target_description,
        source_type=source_type,
        source_id=source_id,
        payload_json=payload_json,
    )
    session.add(row)
    session.flush()
    return row


def get_work_order_by_id(
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
) -> list[WorkOrder]:
    stmt = select(WorkOrder).where(WorkOrder.tenant_id == tenant_id)
    if status:
        stmt = stmt.where(WorkOrder.status == status)
    if order_type:
        stmt = stmt.where(WorkOrder.order_type == order_type)
    stmt = stmt.order_by(WorkOrder.created_at.desc(), WorkOrder.id.desc())
    return list(session.scalars(stmt).all())
