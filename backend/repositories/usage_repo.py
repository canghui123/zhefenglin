"""Repository for usage events and monthly cost snapshots."""
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.usage import CostSnapshot, UsageEvent


def create_usage_event(
    session: Session,
    *,
    tenant_id: int,
    user_id: Optional[int],
    module: str,
    action: str,
    resource_type: str,
    quantity: float,
    unit_cost_internal: float,
    unit_price_external: float,
    estimated_cost_total: float,
    request_id: Optional[str] = None,
    related_object_type: Optional[str] = None,
    related_object_id: Optional[str] = None,
    metadata_json: Optional[str] = None,
) -> UsageEvent:
    row = UsageEvent(
        tenant_id=tenant_id,
        user_id=user_id,
        module=module,
        action=action,
        resource_type=resource_type,
        quantity=quantity,
        unit_cost_internal=unit_cost_internal,
        unit_price_external=unit_price_external,
        estimated_cost_total=estimated_cost_total,
        request_id=request_id,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        metadata_json=metadata_json,
    )
    session.add(row)
    session.flush()
    return row


def list_usage_events_for_period(
    session: Session,
    *,
    tenant_id: int,
    start_at: datetime,
    end_at: datetime,
    resource_type: Optional[str] = None,
) -> list[UsageEvent]:
    stmt = (
        select(UsageEvent)
        .where(UsageEvent.tenant_id == tenant_id)
        .where(UsageEvent.created_at >= start_at)
        .where(UsageEvent.created_at < end_at)
        .order_by(UsageEvent.id)
    )
    if resource_type is not None:
        stmt = stmt.where(UsageEvent.resource_type == resource_type)
    return list(session.scalars(stmt).all())


def get_cost_snapshot(
    session: Session, *, tenant_id: int, month: str
) -> Optional[CostSnapshot]:
    stmt = (
        select(CostSnapshot)
        .where(CostSnapshot.tenant_id == tenant_id)
        .where(CostSnapshot.month == month)
        .limit(1)
    )
    return session.scalars(stmt).first()


def create_cost_snapshot(session: Session, *, tenant_id: int, month: str) -> CostSnapshot:
    row = CostSnapshot(tenant_id=tenant_id, month=month)
    session.add(row)
    session.flush()
    return row


def list_cost_snapshots(
    session: Session, *, month: Optional[str] = None, tenant_id: Optional[int] = None
) -> list[CostSnapshot]:
    stmt = select(CostSnapshot).order_by(CostSnapshot.id)
    if month is not None:
        stmt = stmt.where(CostSnapshot.month == month)
    if tenant_id is not None:
        stmt = stmt.where(CostSnapshot.tenant_id == tenant_id)
    return list(session.scalars(stmt).all())
