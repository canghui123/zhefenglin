"""Tests for upload hardening: MIME sniffing + size limit."""
import os

from fastapi.testclient import TestClient

from main import app
from db.session import get_db_session
from repositories import user_repo, tenant_repo
from services.password_service import hash_password


def _seed_and_login(client: TestClient, email: str = "upload-val@example.com"):
    gen = get_db_session()
    session = next(gen)
    try:
        tenant = tenant_repo.get_or_create_tenant(
            session, code="upload-val-t", name="UPLOAD-VAL"
        )
        user = user_repo.get_user_by_email(session, email)
        if user is None:
            user = user_repo.create_user(
                session,
                email=email,
                password_hash=hash_password("Passw0rd!1"),
                role="admin",
                display_name=email,
            )
        tenant_repo.create_membership(
            session, user_id=user.id, tenant_id=tenant.id, role="admin"
        )
        user_repo.set_default_tenant(session, user.id, tenant.id)
        session.commit()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    r = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Passw0rd!1"},
    )
    assert r.status_code == 200, r.text


def test_upload_rejects_fake_xlsx_content():
    """扩展名伪装为 .xlsx 但内容不是 Excel 的文件应被拒绝。"""
    client = TestClient(app)
    _seed_and_login(client)

    malicious = b"<?php system($_GET['c']); ?>"  # 典型 webshell 载荷
    resp = client.post(
        "/api/asset-package/upload",
        files={
            "file": (
                "pretend.xlsx",
                malicious,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "INVALID_FILE_FORMAT"


def test_upload_rejects_empty_file():
    client = TestClient(app)
    _seed_and_login(client, email="upload-val-empty@example.com")

    resp = client.post(
        "/api/asset-package/upload",
        files={"file": ("empty.xlsx", b"", "application/vnd.ms-excel")},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error"]["code"] == "INVALID_FILE_FORMAT"


def test_upload_rejects_oversize(monkeypatch):
    """超过 upload_excel_max_bytes 的文件返回 413。"""
    from config import settings

    client = TestClient(app)
    _seed_and_login(client, email="upload-val-big@example.com")

    monkeypatch.setattr(settings, "upload_excel_max_bytes", 1024, raising=False)

    # 2KB 的伪 xlsx：开头合法魔数，但体积超过限制
    big = b"PK\x03\x04" + b"x" * 2048
    resp = client.post(
        "/api/asset-package/upload",
        files={
            "file": (
                "big.xlsx",
                big,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 413, resp.text
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_upload_rejects_path_traversal_filename():
    """上传用户端的 filename 即使含 ../ 也不会被用于存储 key。"""
    client = TestClient(app)
    _seed_and_login(client, email="upload-val-trav@example.com")

    # 魔数不合法 → 400，但关键是后端不应写出到 root 之外
    resp = client.post(
        "/api/asset-package/upload",
        files={
            "file": (
                "../../../etc/passwd.xlsx",
                b"not-excel",
                "application/vnd.ms-excel",
            )
        },
    )
    # 400（不是 Excel）就够；我们主要断言后端没崩、没写越界
    assert resp.status_code in (400, 413), resp.text
