from typing import Optional

from sqlalchemy import select

from db.models.plan import Plan
from db.models.subscription import TenantSubscription
from db.session import get_sessionmaker, reset_engine
from repositories import tenant_repo, user_repo
from scripts.seed_commercial_defaults import seed_defaults


def make_session():
    reset_engine()
    SessionLocal = get_sessionmaker()
    return SessionLocal()


def create_tenant(session, *, code: str = "tenant-a", name: str = "Tenant A"):
    tenant = tenant_repo.get_or_create_tenant(session, code=code, name=name)
    session.flush()
    return tenant


def create_user(session, *, email: str, role: str = "manager"):
    user = user_repo.create_user(
        session,
        email=email,
        password_hash="not-used-in-service-tests",
        role=role,
        display_name=email.split("@")[0],
    )
    session.flush()
    return user


def seed_subscription(
    session,
    *,
    tenant_id: int,
    plan_code: str = "standard",
    monthly_budget_limit: float = 5000,
    alert_threshold_percent: float = 80,
    created_by: Optional[int] = None,
):
    seed_defaults(session)
    plan = session.scalars(select(Plan).where(Plan.code == plan_code).limit(1)).first()
    subscription = TenantSubscription(
        tenant_id=tenant_id,
        plan_id=plan.id,
        status="active",
        monthly_budget_limit=monthly_budget_limit,
        alert_threshold_percent=alert_threshold_percent,
        created_by=created_by,
        is_current=True,
    )
    session.add(subscription)
    session.flush()
    return subscription
