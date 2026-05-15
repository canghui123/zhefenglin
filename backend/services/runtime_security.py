"""Runtime security checks for production-like environments.

启动时对关键安全配置做严格校验；任一项不通过则拒绝启动。
所有校验仅在 APP_ENV in {production, staging} 时激活。
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from config import (
    DEFAULT_JWT_REFRESH_SECRET,
    DEFAULT_JWT_SECRET,
    settings,
)


PRODUCTION_LIKE_ENVS = {"production", "staging"}

# 常见占位符关键词，任何密钥/密码字段包含则视为未配置。
_PLACEHOLDER_PATTERNS = (
    "change-me",
    "change_me",
    "changeme",
    "your-",
    "your_",
    "dev-only",
    "example",
    "placeholder",
    "todo",
    "xxx",
)

# 生产环境对称密钥最小长度（字符数）。64 字符 ≈ 32 字节熵，足够 HMAC-SHA256。
_MIN_SECRET_LENGTH = 64


def is_production_like() -> bool:
    return (settings.app_env or "").strip().lower() in PRODUCTION_LIKE_ENVS


def _looks_like_placeholder(value: str) -> bool:
    if not value:
        return True
    lowered = value.lower()
    return any(pat in lowered for pat in _PLACEHOLDER_PATTERNS)


def _check_secret(name: str, value: str, *, min_length: int, issues: list[str]) -> None:
    if _looks_like_placeholder(value):
        issues.append(f"{name} 仍是占位符/默认值")
        return
    if len(value) < min_length:
        issues.append(f"{name} 长度不足 {min_length} 字符（当前 {len(value)}），熵不够")


def _check_database_url(url: str, issues: list[str]) -> None:
    if not url:
        issues.append("DATABASE_URL 未配置")
        return
    try:
        parsed = urlsplit(url)
    except ValueError:
        issues.append("DATABASE_URL 格式无法解析")
        return

    # 默认开发凭据
    if parsed.username in {"app", "postgres", "root"} and parsed.password in {
        "app",
        "postgres",
        "root",
        "password",
        "123456",
    }:
        issues.append("DATABASE_URL 仍在使用默认/弱凭据")

    if parsed.hostname in {"localhost", "127.0.0.1"} and is_production_like():
        # 生产环境通常走容器内主机名，不建议本机直连
        issues.append("DATABASE_URL 主机不应为 localhost（生产应走私网/容器 DNS）")

    if parsed.password and _looks_like_placeholder(parsed.password):
        issues.append("DATABASE_URL 密码包含占位符关键词")


def _check_cors(origins: str, issues: list[str]) -> None:
    if not origins:
        issues.append("CORS_ORIGINS 未配置")
        return
    parts = [o.strip() for o in origins.split(",") if o.strip()]
    if "*" in parts:
        issues.append("CORS_ORIGINS 不能包含通配符 *")
    if any("localhost" in p or "127.0.0.1" in p for p in parts):
        issues.append("CORS_ORIGINS 不应包含 localhost/127.0.0.1")
    if any(not re.match(r"^https://", p) for p in parts):
        issues.append("CORS_ORIGINS 必须全部以 https:// 开头")


def _check_storage(issues: list[str]) -> None:
    backend = (settings.storage_backend or "").strip().lower()
    if backend != "s3":
        issues.append("生产环境 STORAGE_BACKEND 必须为 s3（禁止 local）")
        return
    for field, value in (
        ("S3_ACCESS_KEY", settings.s3_access_key),
        ("S3_SECRET_KEY", settings.s3_secret_key),
        ("S3_BUCKET", settings.s3_bucket),
    ):
        if not value or _looks_like_placeholder(value):
            issues.append(f"{field} 未配置或是占位符")


def validate_runtime_security() -> None:
    if not is_production_like():
        return

    issues: list[str] = []

    # ── JWT 对称密钥 ──
    if settings.jwt_secret == DEFAULT_JWT_SECRET:
        issues.append("JWT_SECRET 仍在使用默认开发值")
    else:
        _check_secret("JWT_SECRET", settings.jwt_secret,
                      min_length=_MIN_SECRET_LENGTH, issues=issues)

    if settings.jwt_refresh_secret == DEFAULT_JWT_REFRESH_SECRET:
        issues.append("JWT_REFRESH_SECRET 仍在使用默认开发值")
    else:
        _check_secret("JWT_REFRESH_SECRET", settings.jwt_refresh_secret,
                      min_length=_MIN_SECRET_LENGTH, issues=issues)

    if (
        settings.jwt_secret
        and settings.jwt_refresh_secret
        and settings.jwt_secret == settings.jwt_refresh_secret
    ):
        issues.append("JWT_SECRET 与 JWT_REFRESH_SECRET 不能相同")

    # ── 数据库 ──
    _check_database_url(settings.database_url, issues)

    # ── CORS ──
    _check_cors(settings.cors_origins, issues)

    # ── 对象存储 ──
    _check_storage(issues)

    # ── 速率限制 ──
    if not settings.rate_limit_enabled:
        issues.append("生产环境 RATE_LIMIT_ENABLED 必须为 true")

    if issues:
        raise RuntimeError("生产环境安全配置无效: " + "；".join(issues))
