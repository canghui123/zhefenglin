import os

from fastapi.testclient import TestClient

from config import settings
from main import app
from repositories import user_repo
from services.password_service import hash_password
from services.rate_limit_service import reset_rate_limits
from tests.conftest import _seed_user


SAMPLE_EXCEL = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "sample_asset_package.xlsx"
)


def test_login_is_rate_limited_after_threshold(monkeypatch):
    _seed_user(email="rate-limit@example.com", password="Passw0rd!1", role="admin")
    client = TestClient(app)
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 60)
    monkeypatch.setattr(settings, "rate_limit_login_max_requests", 2)
    reset_rate_limits()

    first = client.post(
        "/api/auth/login",
        json={"email": "rate-limit@example.com", "password": "wrong-password"},
    )
    second = client.post(
        "/api/auth/login",
        json={"email": "rate-limit@example.com", "password": "wrong-password"},
    )
    third = client.post(
        "/api/auth/login",
        json={"email": "rate-limit@example.com", "password": "wrong-password"},
    )

    assert first.status_code == 401, first.text
    assert second.status_code == 401, second.text
    assert third.status_code == 429, third.text
    body = third.json()
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_asset_upload_is_rate_limited_after_threshold(monkeypatch, authed_client):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 60)
    monkeypatch.setattr(settings, "rate_limit_write_max_requests", 1)
    reset_rate_limits()

    with open(SAMPLE_EXCEL, "rb") as first_file:
        first = authed_client.post(
            "/api/asset-package/upload",
            files={
                "file": (
                    "first.xlsx",
                    first_file,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )
    with open(SAMPLE_EXCEL, "rb") as second_file:
        second = authed_client.post(
            "/api/asset-package/upload",
            files={
                "file": (
                    "second.xlsx",
                    second_file,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )

    assert first.status_code == 200, first.text
    assert second.status_code == 429, second.text
    body = second.json()
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
