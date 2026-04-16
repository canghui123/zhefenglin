from fastapi.testclient import TestClient
from sqlalchemy import select

from db.models.plan import Plan
from db.models.subscription import TenantSubscription
from db.session import get_db_session
from main import app
from repositories import tenant_repo, user_repo
from scripts.seed_commercial_defaults import seed_defaults
from services.password_service import hash_password


def seed_user_and_login(email: str, *, role: str = "admin", tenant_code: str = "default"):
    gen = get_db_session()
    session = next(gen)
    try:
        seed_defaults(session)
        tenant = tenant_repo.get_or_create_tenant(
            session, code=tenant_code, name=tenant_code.upper()
        )
        user = user_repo.get_user_by_email(session, email)
        if user is None:
            user = user_repo.create_user(
                session,
                email=email,
                password_hash=hash_password("Passw0rd!"),
                role=role,
                display_name=email,
            )
        else:
            user.role = role
            user.password_hash = hash_password("Passw0rd!")
        tenant_repo.create_membership(session, user_id=user.id, tenant_id=tenant.id, role=role)
        user_repo.set_default_tenant(session, user.id, tenant.id)
        session.commit()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    client = TestClient(app)
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Passw0rd!"},
    )
    assert response.status_code == 200, response.text
    return client


def seed_subscription(
    *,
    tenant_code: str = "default",
    plan_code: str = "standard",
    monthly_budget_limit: float = 5000,
):
    gen = get_db_session()
    session = next(gen)
    try:
        seed_defaults(session)
        tenant = tenant_repo.get_or_create_tenant(
            session, code=tenant_code, name=tenant_code.upper()
        )
        plan = session.scalars(select(Plan).where(Plan.code == plan_code).limit(1)).first()
        current = session.scalars(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant.id)
            .where(TenantSubscription.is_current.is_(True))
            .limit(1)
        ).first()
        if current is not None:
            current.is_current = False
        session.add(
            TenantSubscription(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status="active",
                monthly_budget_limit=monthly_budget_limit,
                alert_threshold_percent=80,
                is_current=True,
            )
        )
        session.commit()
        return tenant.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass
