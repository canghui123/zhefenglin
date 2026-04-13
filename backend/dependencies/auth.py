"""Request dependencies for authentication and RBAC.

Usage in routers::

    from dependencies.auth import get_current_user, require_role

    @router.get("/portfolio/manager-playbook")
    def manager_playbook(user = Depends(require_role("manager"))):
        ...

The token is read from one of (in order):
    1. `Authorization: Bearer <token>` header
    2. `session` HTTP-only cookie

This dual-source approach lets us use the same dependency for the
TestClient (Bearer header) and the browser (cookie).
"""
from __future__ import annotations

from typing import Callable, Optional

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from db.models.role import role_rank
from db.models.user import User
from db.session import get_db_session
from errors import Unauthorized, Forbidden
from services.auth_service import AuthError, resolve_session


SESSION_COOKIE_NAME = "session"


def _extract_token(request: Request) -> Optional[str]:
    auth_header = request.headers.get("authorization") or request.headers.get(
        "Authorization"
    )
    if auth_header:
        scheme, _, value = auth_header.partition(" ")
        if scheme.lower() == "bearer" and value:
            return value.strip()
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie_token:
        return cookie_token
    return None


def get_current_user(
    request: Request,
    session: Session = Depends(get_db_session),
) -> User:
    token = _extract_token(request)
    if not token:
        raise Unauthorized("未登录")
    try:
        return resolve_session(session, token)
    except AuthError as exc:
        raise Unauthorized(f"会话无效: {exc}")


def require_role(min_role: str) -> Callable[..., User]:
    """Return a dependency that allows users with `min_role` or higher.

    Hierarchy: admin > manager > operator > viewer.
    """
    needed = role_rank(min_role)
    if needed == 0:
        raise ValueError(f"unknown role: {min_role}")

    def _dep(user: User = Depends(get_current_user)) -> User:
        if role_rank(user.role) < needed:
            raise Forbidden()
        return user

    return _dep


def require_any_role(*roles: str) -> Callable[..., User]:
    """Return a dependency that allows any of the listed roles."""
    role_set = set(roles)
    if not role_set:
        raise ValueError("require_any_role needs at least one role")

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in role_set:
            raise Forbidden()
        return user

    return _dep
