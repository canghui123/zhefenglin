"""B4 — env_drift_check 单元测试。

集中验证纯函数逻辑(hash、单项检查的分支),不实际起 postgres / S3。
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

# 让测试能 import scripts/env_drift_check
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from scripts import env_drift_check  # noqa: E402


# ============================================================
# compute_env_hash —— 关键 env 变化触发 hash 变化
# ============================================================

def test_env_hash_changes_when_database_url_changes():
    """改 DATABASE_URL → hash 不同."""
    from scripts.env_drift_check import compute_env_hash

    with patch("config.settings") as s:
        s.database_url = "postgresql://a@h/db1"
        s.jwt_secret = "x"
        s.jwt_refresh_secret = "y"
        s.s3_endpoint = ""
        s.s3_access_key = ""
        s.s3_secret_key = ""
        s.s3_bucket = ""
        s.storage_backend = "local"
        s.che300_mode = "auto"
        s.che300_access_key = ""
        s.app_env = "production"
        h1 = compute_env_hash()

        s.database_url = "postgresql://a@h/db2"
        h2 = compute_env_hash()

    assert h1 != h2, "DATABASE_URL 变化应导致 hash 变化"


def test_env_hash_stable_when_unrelated_var_changes():
    """改无关 env(如 rate_limit_*)→ hash 不变."""
    from scripts.env_drift_check import compute_env_hash

    with patch("config.settings") as s:
        s.database_url = "postgresql://a@h/db"
        s.jwt_secret = "x"
        s.jwt_refresh_secret = "y"
        s.s3_endpoint = ""
        s.s3_access_key = ""
        s.s3_secret_key = ""
        s.s3_bucket = ""
        s.storage_backend = "local"
        s.che300_mode = "auto"
        s.che300_access_key = ""
        s.app_env = "production"
        h1 = compute_env_hash()
        h2 = compute_env_hash()
    assert h1 == h2, "完全相同的 settings 应产生相同的 hash"


# ============================================================
# check_che300 —— 应识别占位符 / 真 key / mock 模式
# ============================================================

def test_check_che300_recognizes_placeholder_as_mock():
    """占位符 key + auto 模式 → 报告"将走 mock"."""
    with patch("config.settings") as s, patch("services.che300_client.settings", s):
        s.che300_mode = "auto"
        s.che300_access_key = "disabled_for_demo"
        s.che300_access_secret = "disabled_for_demo"
        passed, msg = env_drift_check.check_che300()
    assert passed is True
    assert "mock" in msg.lower()


def test_check_che300_recognizes_explicit_mock_mode():
    """显式 mock 模式 → 不管 key 是什么都走 mock."""
    with patch("config.settings") as s, patch("services.che300_client.settings", s):
        s.che300_mode = "mock"
        s.che300_access_key = "real_che300_2026_production_xxx"
        s.che300_access_secret = "real_secret"
        passed, msg = env_drift_check.check_che300()
    assert passed is True
    assert "mock" in msg.lower()


def test_check_che300_recognizes_real_api_with_real_key():
    """auto + 真实 key → 走真 API."""
    with patch("config.settings") as s, patch("services.che300_client.settings", s):
        s.che300_mode = "auto"
        s.che300_access_key = "5AxcA4Vy"  # 看起来像真 key
        s.che300_access_secret = "valid_secret"
        passed, msg = env_drift_check.check_che300()
    assert passed is True
    assert "真车300" in msg or "real" in msg.lower()


# ============================================================
# check_storage_writable —— S3 模式跳过,local 模式实际写
# ============================================================

def test_check_storage_writable_skips_in_s3_mode():
    """S3 模式时跳过本地路径检查."""
    with patch("config.settings") as s:
        s.storage_backend = "s3"
        s.upload_dir = "/nonexistent/path"
        passed, msg = env_drift_check.check_storage_writable()
    assert passed is True
    assert "跳过" in msg


def test_check_storage_writable_writes_local_tmp_file(tmp_path):
    """local 模式时实际写测试文件并清理."""
    with patch("config.settings") as s:
        s.storage_backend = "local"
        s.upload_dir = str(tmp_path)
        passed, msg = env_drift_check.check_storage_writable()
    assert passed is True
    # 测试文件应该已经被清理
    assert not (tmp_path / ".drift_check_test").exists()


# ============================================================
# check_cors_origins —— production 模式严格,development 跳过
# ============================================================

def test_check_cors_skips_in_development():
    """development 模式直接通过."""
    with patch("config.settings") as s:
        s.app_env = "development"
        s.cors_origins = "http://localhost:3000"
        passed, msg = env_drift_check.check_cors_origins()
    assert passed is True
    assert "跳过" in msg


def test_check_cors_rejects_localhost_in_production():
    """production 模式 CORS 含 localhost → 失败."""
    with patch("config.settings") as s:
        s.app_env = "production"
        s.cors_origins = "https://zhefenglin.com,http://localhost:3000"
        passed, msg = env_drift_check.check_cors_origins()
    assert passed is False
    assert "localhost" in msg


def test_check_cors_accepts_proper_production_origins():
    """production + 正经域名 → 通过."""
    with patch("config.settings") as s:
        s.app_env = "production"
        s.cors_origins = "https://zhefenglin.com,https://www.zhefenglin.com"
        passed, msg = env_drift_check.check_cors_origins()
    assert passed is True


# ============================================================
# check_database 异常被捕获(不抛出来终止整个 check)
# ============================================================

def test_check_database_catches_exceptions_gracefully():
    """连接失败时返回 (False, error_msg),不抛异常。"""
    # 用真实但非法的 URL 触发 connect 失败 + 5s timeout
    with patch("config.settings") as s:
        s.database_url = "postgresql+psycopg://x:y@127.0.0.1:1/nonexistent_db"
        passed, msg = env_drift_check.check_database()
    assert passed is False
    assert "失败" in msg
