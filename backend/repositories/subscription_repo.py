"""Repository for subscriptions and feature entitlements."""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.subscription import FeatureEntitlement, TenantSubscription


def get_current_subscription(
    session: Session, *, tenant_id: int, active_only: bool = True
) -> Optional[TenantSubscription]:
    stmt = (
        select(TenantSubscription)
        .where(TenantSubscription.tenant_id == tenant_id)
        .where(TenantSubscription.is_current.is_(True))
        .order_by(TenantSubscription.id.desc())
        .limit(1)
    )
    if active_only:
        stmt = stmt.where(TenantSubscription.status == "active")
    return session.scalars(stmt).first()


def list_current_subscriptions(
    session: Session, *, tenant_id: Optional[int] = None
) -> List[TenantSubscription]:
    stmt = (
        select(TenantSubscription)
        .where(TenantSubscription.is_current.is_(True))
        .order_by(TenantSubscription.id.desc())
    )
    if tenant_id is not None:
        stmt = stmt.where(TenantSubscription.tenant_id == tenant_id)
    return list(session.scalars(stmt).all())


def upsert_current_subscription(
    session: Session,
    *,
    tenant_id: int,
    plan_id: int,
    status: str = "active",
    monthly_budget_limit: float = 0,
    alert_threshold_percent: float = 80,
    created_by: Optional[int] = None,
) -> TenantSubscription:
    current = get_current_subscription(session, tenant_id=tenant_id, active_only=False)
    if current is not None:
        current.plan_id = plan_id
        current.status = status
        current.monthly_budget_limit = monthly_budget_limit
        current.alert_threshold_percent = alert_threshold_percent
        current.created_by = created_by
        current.is_current = True
        session.flush()
        return current
    row = TenantSubscription(
        tenant_id=tenant_id,
        plan_id=plan_id,
        status=status,
        monthly_budget_limit=monthly_budget_limit,
        alert_threshold_percent=alert_threshold_percent,
        created_by=created_by,
        is_current=True,
    )
    session.add(row)
    session.flush()
    return row


def list_feature_entitlements(
    session: Session,
    *,
    plan_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
) -> List[FeatureEntitlement]:
    stmt = select(FeatureEntitlement).order_by(FeatureEntitlement.id)
    if plan_id is not None:
        stmt = stmt.where(FeatureEntitlement.plan_id == plan_id)
    if tenant_id is not None:
        stmt = stmt.where(FeatureEntitlement.tenant_id == tenant_id)
    return list(session.scalars(stmt).all())


def get_feature_entitlement(
    session: Session,
    *,
    feature_key: str,
    plan_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
) -> Optional[FeatureEntitlement]:
    stmt = (
        select(FeatureEntitlement)
        .where(FeatureEntitlement.feature_key == feature_key)
        .order_by(FeatureEntitlement.id.desc())
        .limit(1)
    )
    if plan_id is not None:
        stmt = stmt.where(FeatureEntitlement.plan_id == plan_id)
    if tenant_id is not None:
        stmt = stmt.where(FeatureEntitlement.tenant_id == tenant_id)
    return session.scalars(stmt).first()


def replace_feature_entitlement(
    session: Session,
    *,
    scope: str,
    feature_key: str,
    is_enabled: Optional[bool],
    plan_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
    config_json: Optional[str] = None,
) -> Optional[FeatureEntitlement]:
    stmt = select(FeatureEntitlement).where(FeatureEntitlement.feature_key == feature_key)
    if plan_id is not None:
        stmt = stmt.where(FeatureEntitlement.plan_id == plan_id)
    if tenant_id is not None:
        stmt = stmt.where(FeatureEntitlement.tenant_id == tenant_id)

    for row in session.scalars(stmt).all():
        session.delete(row)
    session.flush()

    if is_enabled is None:
        return None

    row = FeatureEntitlement(
        scope=scope,
        plan_id=plan_id,
        tenant_id=tenant_id,
        feature_key=feature_key,
        is_enabled=bool(is_enabled),
        config_json=config_json,
    )
    session.add(row)
    session.flush()
    return row
