"""Repository helpers for tenant deployment profiles."""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.models.deployment_profile import TenantDeploymentProfile


def get_profile_by_tenant_id(
    session: Session, *, tenant_id: int
) -> Optional[TenantDeploymentProfile]:
    stmt = (
        select(TenantDeploymentProfile)
        .where(TenantDeploymentProfile.tenant_id == tenant_id)
        .limit(1)
    )
    return session.scalars(stmt).first()


def list_profiles(session: Session) -> List[TenantDeploymentProfile]:
    # Keep the admin list stable and tenant-oriented rather than relying on insert order.
    stmt = select(TenantDeploymentProfile).order_by(TenantDeploymentProfile.tenant_id.asc())
    return list(session.scalars(stmt).all())


def upsert_profile(
    session: Session,
    *,
    tenant_id: int,
    **fields,
) -> TenantDeploymentProfile:
    row = get_profile_by_tenant_id(session, tenant_id=tenant_id)
    if row is not None:
        for key, value in fields.items():
            if key == "tenant_id":
                continue
            setattr(row, key, value)
        session.flush()
        return row

    try:
        with session.begin_nested():
            row = TenantDeploymentProfile(tenant_id=tenant_id, **fields)
            session.add(row)
            session.flush()
    except IntegrityError:
        row = get_profile_by_tenant_id(session, tenant_id=tenant_id)
        if row is None:
            raise
        for key, value in fields.items():
            if key == "tenant_id":
                continue
            setattr(row, key, value)
        session.flush()
    return row
