"""Tests for the access-request (申请制内测) endpoint."""
from fastapi.testclient import TestClient

from main import app
from db.session import get_db_session
from db.models.access_request import AccessRequest


def _count_requests() -> int:
    gen = get_db_session()
    session = next(gen)
    try:
        return session.query(AccessRequest).count()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_access_request_accepts_valid_submission():
    client = TestClient(app)

    r = client.post(
        "/api/auth/access-request",
        json={
            "email": "lead@example.com",
            "company": "某某资产管理",
            "contact_name": "张先生",
            "phone": "13800000000",
            "scenario": "月均处置 100 台车",
            "source": "直播",
            "agreed_to_terms": True,
        },
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "accepted"
    assert _count_requests() == 1


def test_access_request_rejects_unchecked_terms():
    client = TestClient(app)
    r = client.post(
        "/api/auth/access-request",
        json={
            "email": "lead2@example.com",
            "company": "公司 B",
            "contact_name": "李女士",
            # agreed_to_terms 默认 False
        },
    )
    assert r.status_code == 400, r.text
    assert _count_requests() == 0


def test_access_request_rejects_bad_email():
    client = TestClient(app)
    r = client.post(
        "/api/auth/access-request",
        json={
            "email": "not-an-email",
            "company": "C",
            "contact_name": "王先生",
            "agreed_to_terms": True,
        },
    )
    assert r.status_code in (400, 422), r.text
    assert _count_requests() == 0


def test_access_request_is_idempotent_per_email():
    """同一邮箱的多次 pending 申请不会被重复落库，但响应仍为 202。"""
    client = TestClient(app)
    payload = {
        "email": "repeat@example.com",
        "company": "D",
        "contact_name": "孙女士",
        "agreed_to_terms": True,
    }
    r1 = client.post("/api/auth/access-request", json=payload)
    r2 = client.post("/api/auth/access-request", json=payload)
    assert r1.status_code == 202
    assert r2.status_code == 202
    assert _count_requests() == 1


def test_access_request_records_terms_version():
    from config import settings

    client = TestClient(app)
    r = client.post(
        "/api/auth/access-request",
        json={
            "email": "terms@example.com",
            "company": "E",
            "contact_name": "赵先生",
            "agreed_to_terms": True,
        },
    )
    assert r.status_code == 202

    gen = get_db_session()
    session = next(gen)
    try:
        row = (
            session.query(AccessRequest)
            .filter(AccessRequest.email == "terms@example.com")
            .one()
        )
        assert row.terms_version == settings.terms_version
        assert row.status == "pending"
    finally:
        try:
            next(gen)
        except StopIteration:
            pass
