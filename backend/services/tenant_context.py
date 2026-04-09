"""Tenant resolution for the request lifetime.

The current strategy is intentionally simple:

1. Every authenticated user has a `default_tenant_id` set at signup time
   (or by an admin). The dependency resolves the tenant from there.
2. If a user belongs to multiple tenants and wants to switch context,
   they pass `X-Tenant-Code` on the request — we look it up and verify
   they have a membership row before honouring it.

A user with no `default_tenant_id` and no `X-Tenant-Code` cannot reach
any business endpoint — better to fail fast than to silently leak data
across tenants.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import get_current_user
from repositories import tenant_repo


TENANT_HEADER = "X-Tenant-Code"


def get_current_tenant_id(
    request: Request,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> int:
    requested_code = request.headers.get(TENANT_HEADER)
    if requested_code:
        tenant = tenant_repo.get_tenant_by_code(session, requested_code.strip())
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="租户不存在",
            )
        if not tenant_repo.has_membership(
            session, user_id=user.id, tenant_id=tenant.id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权访问该租户",
            )
        return tenant.id

    if user.default_tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="未配置默认租户",
        )
    return user.default_tenant_id
