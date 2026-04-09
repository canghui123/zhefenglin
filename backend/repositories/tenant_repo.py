"""Repository for tenants and memberships."""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.membership import Membership
from db.models.tenant import Tenant


# ---------- tenants ----------

def get_tenant_by_id(session: Session, tenant_id: int) -> Optional[Tenant]:
    return session.get(Tenant, tenant_id)


def get_tenant_by_code(session: Session, code: str) -> Optional[Tenant]:
    stmt = select(Tenant).where(Tenant.code == code).limit(1)
    return session.scalars(stmt).first()


def get_or_create_tenant(
    session: Session, *, code: str, name: str, notes: Optional[str] = None
) -> Tenant:
    """Idempotent tenant lookup — used by bootstrap scripts and tests."""
    existing = get_tenant_by_code(session, code)
    if existing is not None:
        return existing
    tenant = Tenant(code=code, name=name, notes=notes, is_active=True)
    session.add(tenant)
    session.flush()
    return tenant


def list_tenants(session: Session) -> List[Tenant]:
    return list(session.scalars(select(Tenant).order_by(Tenant.id)).all())


# ---------- memberships ----------

def create_membership(
    session: Session, *, user_id: int, tenant_id: int, role: str = "viewer"
) -> Membership:
    """Idempotent — adding the same (user, tenant) twice returns the existing row."""
    existing = session.scalars(
        select(Membership)
        .where(Membership.user_id == user_id)
        .where(Membership.tenant_id == tenant_id)
        .limit(1)
    ).first()
    if existing is not None:
        return existing
    row = Membership(user_id=user_id, tenant_id=tenant_id, role=role)
    session.add(row)
    session.flush()
    return row


def list_user_tenants(session: Session, user_id: int) -> List[Tenant]:
    stmt = (
        select(Tenant)
        .join(Membership, Membership.tenant_id == Tenant.id)
        .where(Membership.user_id == user_id)
        .order_by(Tenant.id)
    )
    return list(session.scalars(stmt).all())


def has_membership(session: Session, *, user_id: int, tenant_id: int) -> bool:
    stmt = (
        select(Membership.id)
        .where(Membership.user_id == user_id)
        .where(Membership.tenant_id == tenant_id)
        .limit(1)
    )
    return session.scalars(stmt).first() is not None
