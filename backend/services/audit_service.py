"""Thin wrapper around `repositories.audit_repo` that knows how to pull
context from a FastAPI Request.

Endpoints call `audit_service.record(...)` instead of constructing the
ORM row themselves so we can change the schema in one place and so the
recipe for "where do request_id / ip / user_agent come from" only lives
once.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from db.models.audit_log import AuditLog
from repositories import audit_repo


def _to_json(obj: Optional[Any]) -> Optional[str]:
    if obj is None:
        return None
    if isinstance(obj, str):
        return obj
    try:
        return json.dumps(obj, ensure_ascii=False, default=str)
    except TypeError:
        return json.dumps({"repr": repr(obj)}, ensure_ascii=False)


def record(
    session: Session,
    request: Optional[Request],
    *,
    action: str,
    tenant_id: Optional[int],
    user_id: Optional[int],
    resource_type: Optional[str] = None,
    resource_id: Optional[Any] = None,
    status: str = "success",
    before: Optional[Any] = None,
    after: Optional[Any] = None,
) -> AuditLog:
    """Persist an audit row, pulling request_id/ip/user_agent from `request.state`."""
    request_id: Optional[str] = None
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    if request is not None:
        state = getattr(request, "state", None)
        if state is not None:
            request_id = getattr(state, "request_id", None)
            ip = getattr(state, "client_ip", None)
            user_agent = getattr(state, "user_agent", None)
        if ip is None and request.client is not None:
            ip = request.client.host
        if user_agent is None:
            user_agent = request.headers.get("user-agent")

    return audit_repo.create(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        request_id=request_id,
        ip=ip,
        user_agent=user_agent,
        status=status,
        before_json=_to_json(before),
        after_json=_to_json(after),
    )
