"""接单方(微信小程序 worker)认证依赖。

worker 不进 users/user_sessions 体系,用无状态 JWT:
- token 的 role claim = "worker",sub = worker_id
- 校验签名+过期后,按 id 查 marketplace_workers,要求 is_active
和发布方(tenant 用户)的 cookie/session 体系完全隔离。
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from db.models.marketplace import MarketplaceWorker
from db.session import get_db_session
from errors import Unauthorized
from services.jwt_service import JWTError, decode_access_token, encode_access_token

# worker token 有效期默认 30 天(小程序登录态长)
_WORKER_TTL = timedelta(days=30)


def issue_worker_token(worker: MarketplaceWorker) -> str:
    return encode_access_token(
        user_id=worker.id,
        email=worker.wechat_openid,
        role="worker",
        jti=f"worker-{worker.id}",
        ttl=_WORKER_TTL,
    )


def _extract_bearer(request: Request) -> Optional[str]:
    auth_header = request.headers.get("authorization") or request.headers.get(
        "Authorization"
    )
    if auth_header:
        scheme, _, value = auth_header.partition(" ")
        if scheme.lower() == "bearer" and value:
            return value.strip()
    return None


def get_current_worker(
    request: Request,
    session: Session = Depends(get_db_session),
) -> MarketplaceWorker:
    token = _extract_bearer(request)
    if not token:
        raise Unauthorized("未登录")
    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        raise Unauthorized(f"会话无效: {exc}")

    if payload.get("role") != "worker":
        raise Unauthorized("非接单方令牌")

    try:
        worker_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise Unauthorized("令牌缺少 worker id")

    worker = session.get(MarketplaceWorker, worker_id)
    if worker is None or not worker.is_active:
        raise Unauthorized("接单账号不存在或已停用")
    return worker
