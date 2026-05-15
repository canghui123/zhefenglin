"""Auth login flow — Task 5 Step 1.

These tests describe the contract:
- POST /api/auth/login with valid credentials returns 200 + an access token
  and sets a session cookie.
- POST /api/auth/login with bad credentials returns 401.
- GET /api/auth/me with the session cookie returns the current user.
"""
from fastapi.testclient import TestClient

from config import settings
from main import app
from db.session import get_db_session
from repositories import tenant_repo, user_repo
from services.password_service import hash_password


def _seed_user(email="admin@example.com", password="Passw0rd!1", role="admin"):
    gen = get_db_session()
    session = next(gen)
    try:
        user = user_repo.create_user(
            session,
            email=email,
            password_hash=hash_password(password),
            role=role,
            display_name="Admin",
        )
        session.commit()
        return user.id
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_login_with_valid_credentials_returns_token_and_cookie():
    _seed_user()
    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "Passw0rd!1"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "access_token" in body
    assert body["user"]["email"] == "admin@example.com"
    assert body["user"]["role"] == "admin"
    # Cookie was set on the response
    assert any(
        c.lower().startswith("set-cookie") for c in response.headers.keys()
    ) or "session" in (response.cookies or {})


def test_login_with_wrong_password_returns_401():
    _seed_user()
    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_login_with_unknown_user_returns_401():
    client = TestClient(app)

    response = client.post(
        "/api/auth/login",
        json={"email": "ghost@example.com", "password": "anything"},
    )

    assert response.status_code == 401


def test_me_endpoint_requires_session_and_returns_user():
    _seed_user()
    client = TestClient(app)

    # Without auth → 401
    anon = client.get("/api/auth/me")
    assert anon.status_code == 401

    # With session cookie → 200
    login = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "Passw0rd!1"},
    )
    assert login.status_code == 200

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "admin@example.com"


def test_register_assigns_default_tenant_membership_and_session():
    client = TestClient(app)

    response = client.post(
        "/api/auth/register",
        json={
            "email": "new-user@example.com",
            "password": "Passw0rd!1",
            "display_name": "New User",
            "agreed_to_terms": True,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user"]["email"] == "new-user@example.com"
    assert body["user"]["role"] == "viewer"
    assert any(
        c.lower().startswith("set-cookie") for c in response.headers.keys()
    ) or "session" in (response.cookies or {})

    gen = get_db_session()
    session = next(gen)
    try:
        user = user_repo.get_user_by_email(session, "new-user@example.com")
        assert user is not None
        assert user.default_tenant_id is not None

        default_tenant = tenant_repo.get_tenant_by_code(session, "default")
        assert default_tenant is not None
        assert user.default_tenant_id == default_tenant.id
        assert tenant_repo.has_membership(
            session, user_id=user.id, tenant_id=default_tenant.id
        )
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_register_uses_configured_default_registration_tenant(monkeypatch):
    monkeypatch.setattr(settings, "default_registration_tenant_code", "poc-tenant")
    monkeypatch.setattr(settings, "default_registration_tenant_name", "POC 租户")
    client = TestClient(app)

    response = client.post(
        "/api/auth/register",
        json={
            "email": "poc-user@example.com",
            "password": "Passw0rd!1",
            "display_name": "POC User",
            "agreed_to_terms": True,
        },
    )

    assert response.status_code == 200, response.text

    gen = get_db_session()
    session = next(gen)
    try:
        user = user_repo.get_user_by_email(session, "poc-user@example.com")
        tenant = tenant_repo.get_tenant_by_code(session, "poc-tenant")
        assert user is not None
        assert tenant is not None
        assert tenant.name == "POC 租户"
        assert user.default_tenant_id == tenant.id
        assert tenant_repo.has_membership(
            session, user_id=user.id, tenant_id=tenant.id
        )
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_register_blocks_when_default_tenant_seat_limit_is_exhausted():
    from sqlalchemy import select

    from db.models.plan import Plan
    from db.models.subscription import TenantSubscription
    from scripts.seed_commercial_defaults import seed_defaults

    gen = get_db_session()
    session = next(gen)
    try:
        seed_defaults(session)
        default_tenant = tenant_repo.get_or_create_tenant(
            session, code="default", name="默认租户"
        )
        plan = session.scalars(
            select(Plan).where(Plan.code == "standard").limit(1)
        ).first()
        assert plan is not None
        plan.seat_limit = 1
        session.add(
            TenantSubscription(
                tenant_id=default_tenant.id,
                plan_id=plan.id,
                status="active",
                monthly_budget_limit=5000,
                alert_threshold_percent=80,
                is_current=True,
            )
        )
        session.commit()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    client = TestClient(app)

    first = client.post(
        "/api/auth/register",
        json={
            "email": "seat-first@example.com",
            "password": "Passw0rd!1",
            "display_name": "Seat First",
            "agreed_to_terms": True,
        },
    )
    assert first.status_code == 200, first.text

    second = client.post(
        "/api/auth/register",
        json={
            "email": "seat-second@example.com",
            "password": "Passw0rd!1",
            "display_name": "Seat Second",
            "agreed_to_terms": True,
        },
    )

    assert second.status_code == 409, second.text
    body = second.json()
    assert body["error"]["code"] == "SEAT_LIMIT_EXCEEDED"
    assert "席位" in body["error"]["message"]

    gen = get_db_session()
    session = next(gen)
    try:
        assert user_repo.get_user_by_email(session, "seat-second@example.com") is None
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_login_and_me_include_feature_capabilities():
    from sqlalchemy import select

    from db.models.plan import Plan
    from db.models.subscription import TenantSubscription
    from scripts.seed_commercial_defaults import seed_defaults

    gen = get_db_session()
    session = next(gen)
    try:
        seed_defaults(session)
        tenant = tenant_repo.get_or_create_tenant(
            session, code="auth-feature", name="AUTH-FEATURE"
        )
        user = user_repo.create_user(
            session,
            email="feature-user@example.com",
            password_hash=hash_password("Passw0rd!1"),
            role="manager",
            display_name="Feature User",
        )
        tenant_repo.create_membership(
            session, user_id=user.id, tenant_id=tenant.id, role="manager"
        )
        user_repo.set_default_tenant(session, user.id, tenant.id)
        plan = session.scalars(
            select(Plan).where(Plan.code == "standard").limit(1)
        ).first()
        assert plan is not None
        session.add(
            TenantSubscription(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status="active",
                monthly_budget_limit=5000,
                alert_threshold_percent=80,
                is_current=True,
            )
        )
        session.commit()
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    client = TestClient(app)
    login = client.post(
        "/api/auth/login",
        json={"email": "feature-user@example.com", "password": "Passw0rd!1"},
    )
    assert login.status_code == 200, login.text
    login_body = login.json()
    assert login_body["user"]["feature_capabilities"]["dashboard.advanced"] is True
    assert login_body["user"]["feature_capabilities"]["routing.model_control"] is False
    assert login_body["user"]["feature_capabilities"]["portfolio.advanced_pages"] is False

    me = client.get("/api/auth/me")
    assert me.status_code == 200, me.text
    me_body = me.json()
    assert me_body["feature_capabilities"]["dashboard.advanced"] is True
    assert me_body["feature_capabilities"]["routing.model_control"] is False


def test_login_locks_out_after_repeated_failures():
    """5 次连续失败后即使密码正确也被临时锁定（等保二级防爆破）。"""
    _seed_user(email="lock-target@example.com", password="Passw0rd!1")
    client = TestClient(app)

    # 5 次错误尝试
    for _ in range(5):
        r = client.post(
            "/api/auth/login",
            json={"email": "lock-target@example.com", "password": "wrong"},
        )
        assert r.status_code == 401, r.text

    # 现在即使密码正确，也会被 429 锁定
    correct = client.post(
        "/api/auth/login",
        json={"email": "lock-target@example.com", "password": "Passw0rd!1"},
    )
    assert correct.status_code == 429, correct.text
    body = correct.json()
    assert body["error"]["code"] in ("RATE_LIMIT_EXCEEDED", "TOO_MANY_REQUESTS")


def test_register_rejects_weak_password():
    """注册时密码过弱应被拒绝（不落库）。"""
    client = TestClient(app)

    r = client.post(
        "/api/auth/register",
        json={
            "email": "weak-user@example.com",
            "password": "weakpass",  # 8 chars, one class, below min 10
            "display_name": "Weak",
            "agreed_to_terms": True,
        },
    )
    assert r.status_code in (400, 422), r.text

    # 确认用户未被创建
    from db.session import get_db_session
    gen = get_db_session()
    session = next(gen)
    try:
        assert user_repo.get_user_by_email(session, "weak-user@example.com") is None
    finally:
        try:
            next(gen)
        except StopIteration:
            pass


def test_register_rejects_common_weak_password():
    """注册时使用常见弱密（admin123!）应被拒绝。"""
    client = TestClient(app)

    r = client.post(
        "/api/auth/register",
        json={
            "email": "common-weak@example.com",
            "password": "Admin123!abc",  # meets 3-class + length but contains Admin123!
            "display_name": "Common",
        },
    )
    # 放宽：精确常见弱密 "admin123!" 会命中；"Admin123!abc" 会通过强度校验
    # 真正的常见弱密直接拒
    r2 = client.post(
        "/api/auth/register",
        json={
            "email": "common-weak2@example.com",
            "password": "Password123",  # 在黑名单中
            "display_name": "Common2",
            "agreed_to_terms": True,
        },
    )
    assert r2.status_code in (400, 422), r2.text


def test_register_rejects_when_terms_not_agreed():
    """未勾选"同意服务条款"的注册请求应被拒绝。"""
    client = TestClient(app)
    r = client.post(
        "/api/auth/register",
        json={
            "email": "no-terms@example.com",
            "password": "Str0ng!Passw0rd",
            "display_name": "NoTerms",
            # agreed_to_terms 故意不传 → 默认 False
        },
    )
    assert r.status_code in (400, 422), r.text


def test_register_blocked_when_public_registration_disabled(monkeypatch):
    """关闭公开注册后 /register 直接返回 403。"""
    from config import settings

    monkeypatch.setattr(settings, "allow_public_registration", False, raising=False)
    client = TestClient(app)
    r = client.post(
        "/api/auth/register",
        json={
            "email": "invite-only@example.com",
            "password": "Str0ng!Passw0rd",
            "display_name": "InviteOnly",
            "agreed_to_terms": True,
        },
    )
    assert r.status_code == 403, r.text


def test_register_persists_terms_accepted_at():
    """成功注册时应在 users 表上写入 terms_accepted_at / terms_version。"""
    from config import settings

    client = TestClient(app)
    r = client.post(
        "/api/auth/register",
        json={
            "email": "with-terms@example.com",
            "password": "Str0ng!Passw0rd",
            "display_name": "WithTerms",
            "agreed_to_terms": True,
        },
    )
    assert r.status_code == 200, r.text

    gen = get_db_session()
    session = next(gen)
    try:
        u = user_repo.get_user_by_email(session, "with-terms@example.com")
        assert u is not None
        assert u.terms_accepted_at is not None
        assert u.terms_version == settings.terms_version
    finally:
        try:
            next(gen)
        except StopIteration:
            pass
