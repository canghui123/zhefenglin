#!/usr/bin/env python3
"""B4 — Environment drift detection.

防止 `.env` 改了但容器没重启 / postgres / MinIO 等容器仍用旧凭证的
"配置漂移"问题。这类问题在 2026-05-30 一天内撞了 3 次:

1. DB_PASSWORD 改过 → backend 起不来,alembic 报 auth failed
2. S3_ACCESS_KEY 改过,但 MinIO 6 周前用旧凭证 init → 上传 InvalidAccessKeyId
3. CHE300_ACCESS_KEY="disabled_for_demo" 当成有 key → 真 API 失败 → 估值 0%

本脚本主动验证关键服务连通性 + 业务逻辑分支,失败时退出码 1 并打印
具体哪个配置漂移、怎么修。

使用场景:
    # 1. 容器内手动跑(部署后,smoke-check 之后)
    docker compose exec backend python3 scripts/env_drift_check.py

    # 2. cron 每日跑 / 每次部署后跑
    docker compose exec -T backend python3 scripts/env_drift_check.py >> /var/log/env_drift.log 2>&1

    # 3. 加到 deploy/smoke-check.sh 作为最后一道关
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Callable

# 让脚本能从 backend/scripts/ 直接跑(本地或容器内),不依赖 PYTHONPATH。
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


# ANSI 颜色(在 tty 上着色,管道时自动退化)
def _stylize(prefix: str, code: str) -> str:
    if sys.stdout.isatty():
        return f"\033[{code}m{prefix}\033[0m"
    return prefix


GREEN_CHECK = _stylize("✓", "32")
RED_CROSS = _stylize("✗", "31")
YELLOW_BANG = _stylize("!", "33")
BLUE_INFO = _stylize("i", "34")


# ============================================================
# 单项检查 —— 每个函数返回 (passed: bool, message: str)
# ============================================================

def check_database() -> tuple[bool, str]:
    """实际连 postgres,跑 SELECT 1。捕获 auth_failed / connection refused 等。"""
    try:
        from sqlalchemy import create_engine, text

        from config import settings

        engine = create_engine(
            settings.database_url,
            connect_args={"connect_timeout": 5},
            pool_pre_ping=False,
        )
        with engine.connect() as conn:
            value = conn.execute(text("SELECT 1")).scalar()
        if value != 1:
            return False, f"SELECT 1 返回 {value},应为 1"
        return True, "postgres 连接 + 鉴权 OK"
    except Exception as exc:  # noqa: BLE001
        return False, f"postgres 连接失败: {type(exc).__name__}: {exc}"


def check_s3() -> tuple[bool, str]:
    """实际连 S3/MinIO,list_buckets。"""
    try:
        from config import settings

        if (settings.storage_backend or "local").lower() != "s3":
            return True, f"storage_backend={settings.storage_backend},跳过 S3 检查"

        import boto3

        if not settings.s3_endpoint:
            return False, "STORAGE_BACKEND=s3 但 S3_ENDPOINT 为空"
        if not settings.s3_access_key or not settings.s3_secret_key:
            return False, "STORAGE_BACKEND=s3 但 S3_ACCESS_KEY/SECRET 为空"

        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
        )
        resp = client.list_buckets()
        buckets = [b["Name"] for b in resp.get("Buckets", [])]
        if settings.s3_bucket and settings.s3_bucket not in buckets:
            return False, f"bucket {settings.s3_bucket!r} 不存在(可用: {buckets})"
        return True, f"S3/MinIO 连接 + 鉴权 OK,buckets: {buckets}"
    except Exception as exc:  # noqa: BLE001
        return False, f"S3/MinIO 连接失败: {type(exc).__name__}: {exc}"


def check_jwt() -> tuple[bool, str]:
    """JWT_SECRET 编解码 round-trip,确认 secret 可用 + 算法正常。"""
    try:
        from config import settings
        from services.jwt_service import decode_access_token, encode_access_token

        if not settings.jwt_secret or settings.jwt_secret == "change_me":
            return False, "JWT_SECRET 为空或仍是默认占位符 'change_me'"

        # encode_access_token 需要必填 sentinel 值;我们关心的是签名+解码 round-trip
        token = encode_access_token(
            user_id=99999,
            email="drift-check@example.invalid",
            role="viewer",
            jti="drift-check-jti",
        )
        decoded = decode_access_token(token)
        # JWT 标准用 'sub' 字段存 subject(user_id);decode 后可能是字符串
        if str(decoded.get("sub", "")) != "99999":
            return False, f"JWT round-trip 后 sub 不对: {decoded}"
        return True, "JWT_SECRET 编解码 OK"
    except Exception as exc:  # noqa: BLE001
        return False, f"JWT 检查失败: {type(exc).__name__}: {exc}"


def check_che300() -> tuple[bool, str]:
    """汇报 CHE300 mode 与判定结果,不实际调网络。"""
    try:
        from config import settings
        from services.che300_client import (
            _CHE300_MOCK_PLACEHOLDER_KEYS,
            _should_use_real_che300_api,
        )

        mode = getattr(settings, "che300_mode", "auto")
        will_use_real = _should_use_real_che300_api()
        key = settings.che300_access_key or ""
        key_preview = (key[:8] + "...") if len(key) > 8 else (key or "(空)")
        target = "真车300 API" if will_use_real else "本地 mock fallback"

        # 检测常见反模式:auto 模式 + key 看起来像真 key 但在 placeholder 白名单
        warning = ""
        if mode == "auto" and key and key.lower() in _CHE300_MOCK_PLACEHOLDER_KEYS:
            warning = f"(注:key={key_preview} 被识别为占位符,走 mock)"

        return True, f"CHE300 模式: {mode}, 将走 {target}, key={key_preview}{warning}"
    except Exception as exc:  # noqa: BLE001
        return False, f"CHE300 检查失败: {type(exc).__name__}: {exc}"


def check_storage_writable() -> tuple[bool, str]:
    """如果 storage_backend=local,验证 upload_dir 可写。"""
    try:
        from config import settings

        if (settings.storage_backend or "local").lower() == "s3":
            return True, "storage_backend=s3,跳过本地路径检查"

        path = Path(settings.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".drift_check_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        return True, f"本地 upload_dir 可写: {path}"
    except Exception as exc:  # noqa: BLE001
        return False, f"本地 upload_dir 不可写: {type(exc).__name__}: {exc}"


def check_cors_origins() -> tuple[bool, str]:
    """生产环境不允许 CORS 含 localhost / 127.0.0.1。"""
    try:
        from config import settings

        if (settings.app_env or "development").lower() != "production":
            return True, f"app_env={settings.app_env},跳过 CORS 生产模式检查"

        origins = settings.cors_origins or ""
        bad = [o for o in origins.split(",") if "localhost" in o or "127.0.0.1" in o]
        if bad:
            return False, f"生产环境 CORS_ORIGINS 含本地地址: {bad}"
        return True, f"生产 CORS 已收紧"
    except Exception as exc:  # noqa: BLE001
        return False, f"CORS 检查失败: {type(exc).__name__}: {exc}"


# ============================================================
# Env hash —— 检测 .env 变化(配合容器重启提示)
# ============================================================

def compute_env_hash() -> str:
    """计算关键 env 变量的 sha256。"""
    from config import settings

    critical_vars = {
        "DATABASE_URL": settings.database_url,
        "JWT_SECRET": settings.jwt_secret,
        "JWT_REFRESH_SECRET": settings.jwt_refresh_secret,
        "S3_ENDPOINT": settings.s3_endpoint or "",
        "S3_ACCESS_KEY": settings.s3_access_key or "",
        "S3_SECRET_KEY": settings.s3_secret_key or "",
        "S3_BUCKET": settings.s3_bucket or "",
        "STORAGE_BACKEND": settings.storage_backend,
        "CHE300_MODE": getattr(settings, "che300_mode", "auto"),
        "CHE300_ACCESS_KEY": settings.che300_access_key or "",
        "APP_ENV": settings.app_env,
    }
    blob = "|".join(f"{k}={v}" for k, v in sorted(critical_vars.items()))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _hash_file_path() -> Path:
    """存放 env hash 的位置。容器内 /tmp 重启会丢,这正是我们想要的:
    每次容器重启都重新算 hash 然后写一次,下次跑时对比看是否变化。"""
    return Path(os.environ.get("ENV_DRIFT_HASH_PATH", "/tmp/env_drift_hash.txt"))


# ============================================================
# Runner
# ============================================================

CHECKS: list[tuple[str, Callable[[], tuple[bool, str]]]] = [
    ("DATABASE_URL → postgres 连接", check_database),
    ("S3_ACCESS_KEY → MinIO/S3 连接", check_s3),
    ("JWT_SECRET 编解码", check_jwt),
    ("CHE300_MODE 配置", check_che300),
    ("本地存储可写", check_storage_writable),
    ("CORS 生产模式", check_cors_origins),
]


def main() -> int:
    print("=" * 64)
    print("Environment Drift Check")
    print("=" * 64)

    failed: list[str] = []
    for name, func in CHECKS:
        try:
            passed, msg = func()
        except Exception as exc:  # noqa: BLE001
            passed, msg = False, f"检查器自身异常: {type(exc).__name__}: {exc}"
        prefix = GREEN_CHECK if passed else RED_CROSS
        target = sys.stdout if passed else sys.stderr
        print(f"  {prefix} {name}: {msg}", file=target)
        if not passed:
            failed.append(name)

    print()
    env_hash = compute_env_hash()
    print(f"  {BLUE_INFO} 关键 env 变量 sha256: {env_hash[:16]}...")

    # 对比上次 hash,提示是否需要重启相关容器
    hash_path = _hash_file_path()
    try:
        if hash_path.exists():
            last_hash = hash_path.read_text(encoding="utf-8").strip()
            if last_hash and last_hash != env_hash:
                print(
                    f"  {YELLOW_BANG} 配置自上次检查后变化(上次: {last_hash[:16]}...)",
                    file=sys.stderr,
                )
                print(
                    f"    → 若 .env 改过相关变量,需要重启对应容器:",
                    file=sys.stderr,
                )
                print(
                    f"      docker compose up -d --no-deps backend",
                    file=sys.stderr,
                )
                print(
                    f"    → 注意:postgres / MinIO 数据卷初始化时记录的密码不会自动更新,",
                    file=sys.stderr,
                )
                print(
                    f"      可能需要把 .env 回滚到容器初始化时的值。",
                    file=sys.stderr,
                )
        hash_path.write_text(env_hash + "\n", encoding="utf-8")
    except OSError:
        # 没有 hash 文件目录的写权限 → 算作"软告警",不让整个 check 失败
        pass

    print()
    if failed:
        print(
            f"=== {RED_CROSS} 失败 {len(failed)}/{len(CHECKS)} 项 ===",
            file=sys.stderr,
        )
        for name in failed:
            print(f"  - {name}", file=sys.stderr)
        print()
        print("修复指引:", file=sys.stderr)
        print("  1. 检查 .env 是否最近改过相关变量", file=sys.stderr)
        print("  2. 改了后 'docker compose up -d --no-deps <service>' 重启容器", file=sys.stderr)
        print("  3. postgres / MinIO 数据卷已初始化时,密码不会自动更新", file=sys.stderr)
        print("  4. 不确定时回滚 .env 到上次成功部署的值", file=sys.stderr)
        return 1

    print(f"=== {GREEN_CHECK} 全部 {len(CHECKS)} 项通过 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
