"""Small in-process rate limiter for critical endpoints.

This is intentionally simple: it protects single-instance deployments and
provides a clear extension point for Redis-backed distributed limiting later.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque

from fastapi import Request

from config import settings
from errors import RateLimitExceeded


_BUCKETS: dict[tuple[str, str], Deque[float]] = defaultdict(deque)
_LOCK = Lock()


def _client_id(request: Request) -> str:
    state = getattr(request, "state", None)
    if state is not None and getattr(state, "client_ip", None):
        return str(state.client_ip)
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


def enforce_request_limit(
    request: Request,
    *,
    scope: str,
    limit: int,
) -> dict[str, int | str]:
    if not settings.rate_limit_enabled or limit <= 0:
        return {"scope": scope, "limit": limit, "remaining": limit}

    window_seconds = max(int(settings.rate_limit_window_seconds or 60), 1)
    client_id = _client_id(request)
    bucket_key = (scope, client_id)
    now = time.monotonic()

    with _LOCK:
        bucket = _BUCKETS[bucket_key]
        while bucket and now - bucket[0] >= window_seconds:
            bucket.popleft()

        if len(bucket) >= limit:
            retry_after = max(int(window_seconds - (now - bucket[0])), 1)
            raise RateLimitExceeded(
                details={
                    "scope": scope,
                    "limit": limit,
                    "window_seconds": window_seconds,
                    "client_id": client_id,
                    "retry_after_seconds": retry_after,
                }
            )

        bucket.append(now)
        return {
            "scope": scope,
            "limit": limit,
            "remaining": max(limit - len(bucket), 0),
        }


def reset_rate_limits() -> None:
    with _LOCK:
        _BUCKETS.clear()


# ─────────────────────────────────────────────────────────────────────────
# 失败登录锁定：按 (scope, identifier) 记录最近一次锁定开始时间 + 连续失败次数。
# 识别 identifier 建议使用 email，这样可以精确锁定到账号，不影响同 IP 下的其他用户。
# ─────────────────────────────────────────────────────────────────────────

_LOCKOUTS: dict[tuple[str, str], tuple[int, float]] = {}  # (fails, blocked_until_ts)
_LOCKOUT_LOCK = Lock()

DEFAULT_LOCKOUT_THRESHOLD = 5
DEFAULT_LOCKOUT_SECONDS = 15 * 60


def check_and_raise_if_locked(scope: str, identifier: str) -> None:
    """如果该 identifier 已被锁定，抛 RateLimitExceeded。"""
    if not settings.rate_limit_enabled:
        return
    key = (scope, (identifier or "").lower())
    now = time.monotonic()
    with _LOCKOUT_LOCK:
        entry = _LOCKOUTS.get(key)
        if not entry:
            return
        fails, blocked_until = entry
        # blocked_until == 0 表示只是在累计失败次数、还没触发锁定 —— 保留计数
        if blocked_until == 0.0:
            return
        if now < blocked_until:
            retry_after = max(int(blocked_until - now), 1)
            raise RateLimitExceeded(
                detail="登录失败次数过多，账号已临时锁定，请稍后再试",
                details={
                    "scope": scope,
                    "retry_after_seconds": retry_after,
                },
            )
        # 锁定已过期：清理
        _LOCKOUTS.pop(key, None)


def record_login_failure(
    scope: str,
    identifier: str,
    *,
    threshold: int = DEFAULT_LOCKOUT_THRESHOLD,
    lockout_seconds: int = DEFAULT_LOCKOUT_SECONDS,
) -> int:
    """累加失败次数；达到阈值则设置锁定窗口。返回累计失败次数。"""
    if not settings.rate_limit_enabled:
        return 0
    key = (scope, (identifier or "").lower())
    now = time.monotonic()
    with _LOCKOUT_LOCK:
        fails, blocked_until = _LOCKOUTS.get(key, (0, 0.0))
        # 若已过了锁定窗口，从 0 重新计数
        if now >= blocked_until and blocked_until != 0.0:
            fails = 0
        fails += 1
        if fails >= threshold:
            blocked_until = now + lockout_seconds
            _LOCKOUTS[key] = (fails, blocked_until)
        else:
            _LOCKOUTS[key] = (fails, blocked_until)
        return fails


def record_login_success(scope: str, identifier: str) -> None:
    """登录成功：清零锁定状态。"""
    key = (scope, (identifier or "").lower())
    with _LOCKOUT_LOCK:
        _LOCKOUTS.pop(key, None)


def reset_lockouts() -> None:
    with _LOCKOUT_LOCK:
        _LOCKOUTS.clear()
