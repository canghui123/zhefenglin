"""task #5 — 试用 onboarding 单元测试。

覆盖:
- 每个新注册用户独立 tenant(看不到其他用户的数据)
- 自动订阅 trial_poc 套餐 30 天
- 角色 operator
- 试用 tenant 设为该 user 的 default tenant
- 缺套餐种子时报清晰错误
- is_trial_mode_enabled 的 trial/legacy 切换
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from config import settings
from db.models.plan import Plan
from db.models.user import User
from db.session import get_db_session
from repositories import plan_repo, subscription_repo, tenant_repo, user_repo
from services import trial_onboarding
from services.password_service import hash_password


# ============================================================
# Helpers
# ============================================================

def _get_session() -> tuple[Session, object]:
    gen = get_db_session()
    return next(gen), gen


def _close_session(gen) -> None:
    try:
        next(gen)
    except StopIteration:
        pass


def _seed_trial_plan(session: Session) -> Plan:
    """模拟生产 seed_commercial_defaults 写入 trial_poc 套餐。"""
    existing = plan_repo.get_plan_by_code(session, code="trial_poc")
    if existing is not None:
        return existing
    plan = plan_repo.create_plan(
        session,
        code="trial_poc",
        name="Trial / POC",
        billing_cycle_supported="monthly",
        seat_limit=3,
        included_vin_calls=120,
        included_condition_pricing_points=3,
        included_ai_reports=20,
        included_asset_packages=10,
        monthly_price=1999,
        yearly_price=19990,
        setup_fee=0,
        private_deploy_fee=0,
    )
    session.commit()
    return plan


def _create_user(session: Session, email: str, display_name: str) -> User:
    user = user_repo.create_user(
        session,
        email=email,
        password_hash=hash_password("Passw0rd!1"),
        role="viewer",
        display_name=display_name,
    )
    session.commit()
    return user


# ============================================================
# is_trial_mode_enabled
# ============================================================

def test_is_trial_mode_enabled_default_is_true(monkeypatch):
    monkeypatch.setattr(settings, "trial_onboarding_mode", "trial", raising=False)
    assert trial_onboarding.is_trial_mode_enabled() is True


def test_is_trial_mode_legacy_disables_trial(monkeypatch):
    monkeypatch.setattr(settings, "trial_onboarding_mode", "legacy", raising=False)
    assert trial_onboarding.is_trial_mode_enabled() is False


def test_is_trial_mode_handles_uppercase(monkeypatch):
    monkeypatch.setattr(settings, "trial_onboarding_mode", "LEGACY", raising=False)
    assert trial_onboarding.is_trial_mode_enabled() is False


# ============================================================
# create_trial_environment
# ============================================================

def test_create_trial_environment_creates_isolated_tenant():
    """新用户独立 tenant,不和其他 trial 用户共享。"""
    session, gen = _get_session()
    try:
        _seed_trial_plan(session)
        user_a = _create_user(session, "trial-a@example.com", "User A")
        user_b = _create_user(session, "trial-b@example.com", "User B")

        tenant_a = trial_onboarding.create_trial_environment(
            session, user=user_a, display_name="User A"
        )
        tenant_b = trial_onboarding.create_trial_environment(
            session, user=user_b, display_name="User B"
        )

        assert tenant_a.id != tenant_b.id, "两个新用户应该有独立的 tenant"
        assert tenant_a.code != tenant_b.code, "tenant code 必须唯一"
        assert "User A" in tenant_a.name
        assert "User B" in tenant_b.name
    finally:
        _close_session(gen)


def test_create_trial_environment_subscribes_to_trial_poc():
    """自动订阅 trial_poc 套餐,有效期 30 天。"""
    session, gen = _get_session()
    try:
        plan = _seed_trial_plan(session)
        user = _create_user(session, "trial-sub@example.com", "Sub User")

        tenant = trial_onboarding.create_trial_environment(
            session, user=user, display_name="Sub User", trial_days=30
        )
        sub = subscription_repo.get_current_subscription(
            session, tenant_id=tenant.id, active_only=False
        )
        assert sub is not None, "应该自动创建订阅"
        assert sub.plan_id == plan.id, "套餐应该是 trial_poc"
        assert sub.status == "trial"
        # 过期时间应该在 29-31 天后(允许时差)
        assert sub.expires_at is not None
        now = datetime.now(timezone.utc)
        # 兼容数据库可能不存 tz info
        expires_at = sub.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        delta = expires_at - now
        assert timedelta(days=29) <= delta <= timedelta(days=31), \
            f"trial_days=30 应该让 expires_at 在 29-31 天后,实际 {delta}"
    finally:
        _close_session(gen)


def test_create_trial_environment_assigns_operator_role():
    """试用 tenant 内角色 = operator(独立 tenant 内业务最大权限,不给 admin)。"""
    session, gen = _get_session()
    try:
        _seed_trial_plan(session)
        user = _create_user(session, "trial-role@example.com", "Role User")

        tenant = trial_onboarding.create_trial_environment(
            session, user=user, display_name="Role User"
        )
        assert tenant_repo.has_membership(
            session, user_id=user.id, tenant_id=tenant.id
        )
        # 通过 SQL 查 membership 的 role
        from db.models.membership import Membership

        m = (
            session.query(Membership)
            .filter(Membership.user_id == user.id, Membership.tenant_id == tenant.id)
            .first()
        )
        assert m is not None
        assert m.role == "operator", f"试用 tenant 内角色应该是 operator,实际 {m.role}"
    finally:
        _close_session(gen)


def test_create_trial_environment_sets_default_tenant():
    """试用 tenant 自动设为 user 的 default tenant。"""
    session, gen = _get_session()
    try:
        _seed_trial_plan(session)
        user = _create_user(session, "trial-default@example.com", "Default User")
        assert user.default_tenant_id is None

        tenant = trial_onboarding.create_trial_environment(
            session, user=user, display_name="Default User"
        )
        # refresh
        session.flush()
        session.refresh(user)
        assert user.default_tenant_id == tenant.id
    finally:
        _close_session(gen)


def test_create_trial_environment_raises_when_plan_missing():
    """trial_poc 套餐种子缺失 → 清晰错误,提示跑 seed。"""
    session, gen = _get_session()
    try:
        # 不 seed trial_poc 套餐
        user = _create_user(session, "trial-noplan@example.com", "NoPlan User")
        with pytest.raises(ValueError) as exc_info:
            trial_onboarding.create_trial_environment(
                session, user=user, display_name="NoPlan User"
            )
        msg = str(exc_info.value)
        assert "trial_poc" in msg
        assert "seed_commercial_defaults" in msg
    finally:
        _close_session(gen)


def test_create_trial_environment_tenant_code_includes_user_id():
    """tenant code 包含 user_id,便于运维识别。"""
    session, gen = _get_session()
    try:
        _seed_trial_plan(session)
        user = _create_user(session, "trial-code@example.com", "Code User")
        tenant = trial_onboarding.create_trial_environment(
            session, user=user, display_name="Code User"
        )
        assert tenant.code.startswith("trial_")
        assert str(user.id) in tenant.code
    finally:
        _close_session(gen)
