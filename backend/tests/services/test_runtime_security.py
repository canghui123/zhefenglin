import pytest

from config import (
    DEFAULT_JWT_REFRESH_SECRET,
    DEFAULT_JWT_SECRET,
    settings,
)
from services.runtime_security import validate_runtime_security


def _apply_valid_production_settings(monkeypatch):
    """把 settings 模拟成一个合规的生产配置（每个分项都满足校验）。"""
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(
        settings,
        "jwt_secret",
        "a" * 64,  # ≥ 64 字符，非占位符
    )
    monkeypatch.setattr(
        settings,
        "jwt_refresh_secret",
        "b" * 64,
    )
    monkeypatch.setattr(
        settings,
        "database_url",
        "postgresql+psycopg://appuser:Str0ngPa55!@db.internal:5432/auto_finance",
    )
    monkeypatch.setattr(
        settings, "cors_origins", "https://zhefenglin.com,https://www.zhefenglin.com"
    )
    monkeypatch.setattr(settings, "storage_backend", "s3")
    monkeypatch.setattr(settings, "s3_access_key", "RealAccessKey1234567")
    monkeypatch.setattr(settings, "s3_secret_key", "RealSecretKey987654321FullRandom")
    monkeypatch.setattr(settings, "s3_bucket", "auto-finance")
    monkeypatch.setattr(settings, "rate_limit_enabled", True)


def test_runtime_security_rejects_default_jwt_secret_in_production(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "jwt_secret", DEFAULT_JWT_SECRET)
    monkeypatch.setattr(settings, "jwt_refresh_secret", DEFAULT_JWT_REFRESH_SECRET)

    with pytest.raises(RuntimeError):
        validate_runtime_security()


def test_runtime_security_allows_compliant_production_config(monkeypatch):
    _apply_valid_production_settings(monkeypatch)
    validate_runtime_security()


def test_runtime_security_rejects_short_jwt(monkeypatch):
    _apply_valid_production_settings(monkeypatch)
    monkeypatch.setattr(settings, "jwt_secret", "short-but-custom-123456")  # < 64
    with pytest.raises(RuntimeError) as exc:
        validate_runtime_security()
    assert "长度不足" in str(exc.value)


def test_runtime_security_rejects_localhost_db_in_production(monkeypatch):
    _apply_valid_production_settings(monkeypatch)
    monkeypatch.setattr(
        settings,
        "database_url",
        "postgresql+psycopg://appuser:Str0ngPa55!@localhost:5432/auto_finance",
    )
    with pytest.raises(RuntimeError) as exc:
        validate_runtime_security()
    assert "localhost" in str(exc.value)


def test_runtime_security_rejects_wildcard_cors(monkeypatch):
    _apply_valid_production_settings(monkeypatch)
    monkeypatch.setattr(settings, "cors_origins", "*")
    with pytest.raises(RuntimeError) as exc:
        validate_runtime_security()
    assert "CORS_ORIGINS" in str(exc.value)


def test_runtime_security_rejects_local_storage(monkeypatch):
    _apply_valid_production_settings(monkeypatch)
    monkeypatch.setattr(settings, "storage_backend", "local")
    with pytest.raises(RuntimeError) as exc:
        validate_runtime_security()
    assert "STORAGE_BACKEND" in str(exc.value)


def test_runtime_security_rejects_disabled_rate_limit(monkeypatch):
    _apply_valid_production_settings(monkeypatch)
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    with pytest.raises(RuntimeError) as exc:
        validate_runtime_security()
    assert "RATE_LIMIT_ENABLED" in str(exc.value)


def test_runtime_security_rejects_equal_jwt_secrets(monkeypatch):
    _apply_valid_production_settings(monkeypatch)
    same = "x" * 64
    monkeypatch.setattr(settings, "jwt_secret", same)
    monkeypatch.setattr(settings, "jwt_refresh_secret", same)
    with pytest.raises(RuntimeError) as exc:
        validate_runtime_security()
    assert "不能相同" in str(exc.value)
