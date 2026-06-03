"""task #5 — 试用环境一键 onboard。

新注册用户应该看到**自己专属的试用空间**,而不是和其他试用用户共享
default 租户(否则会互相看到对方上传的资产包,SaaS 试用体验崩塌)。

本模块封装"创建试用 tenant + 自动订阅 trial_poc + 设默认 + 加成员"
作为单一 atomic 操作。register endpoint 直接调用,出错则回滚。

设计原则:
- 每个新用户一个独立 tenant: code=`trial_{user_id}_{timestamp}`
- 自动订阅 trial_poc 套餐,30 天试用
- 用户角色 = `operator`(独立 tenant 内的最大业务权限,
  不给 admin 避免试用用户碰到系统管理动作)
- 试用 tenant 自动设为该 user 的 default tenant
- 兼容老逻辑:`TRIAL_ONBOARDING_MODE=legacy` 时退回"挂到 default 租户"
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from config import settings
from db.models.tenant import Tenant
from db.models.user import User
from repositories import plan_repo, subscription_repo, tenant_repo, user_repo


def is_trial_mode_enabled() -> bool:
    """是否启用试用 onboard 模式(默认 True,环境变量可关)。"""
    mode = (getattr(settings, "trial_onboarding_mode", "trial") or "trial").lower().strip()
    return mode != "legacy"


def _generate_trial_tenant_code(user_id: int) -> str:
    """生成唯一的试用 tenant code:`trial_{user_id}_{epoch_seconds}`。"""
    epoch = int(datetime.now(timezone.utc).timestamp())
    return f"trial_{user_id}_{epoch}"


def _format_trial_tenant_name(display_name: str) -> str:
    """`{display_name} 的试用空间`,做适度截断。"""
    base = (display_name or "用户").strip()
    if len(base) > 24:
        base = base[:24]
    return f"{base} 的试用空间"


def create_trial_environment(
    session: Session,
    *,
    user: User,
    display_name: str,
    trial_days: int = 30,
    plan_code: str = "trial_poc",
    monthly_budget_limit: float = 200.0,
) -> Tenant:
    """为新注册用户创建独立试用环境(tenant + subscription + membership)。

    所有操作在同一事务里;调用方负责 commit / rollback。

    返回新创建的 tenant 对象。

    Raises:
        ValueError: trial_poc 套餐种子缺失(应该在 deploy 前跑 seed_commercial_defaults)
    """
    # 1. 试用 tenant —— 唯一 code,人类可读 name
    tenant = tenant_repo.get_or_create_tenant(
        session,
        code=_generate_trial_tenant_code(user.id),
        name=_format_trial_tenant_name(display_name),
    )

    # 2. 把 user 挂到该 tenant,role=operator(独立 tenant 内业务最大权限)
    tenant_repo.create_membership(
        session, user_id=user.id, tenant_id=tenant.id, role="operator"
    )

    # 3. 把试用 tenant 设为该 user 的 default tenant
    user_repo.set_default_tenant(session, user.id, tenant.id)

    # 4. 订阅 trial_poc 套餐,有效期 = trial_days 天
    plan = plan_repo.get_plan_by_code(session, code=plan_code)
    if plan is None:
        raise ValueError(
            f"{plan_code!r} 套餐种子缺失。请在 deploy 时跑 "
            "`python3 scripts/seed_commercial_defaults.py`。"
        )
    subscription = subscription_repo.upsert_current_subscription(
        session,
        tenant_id=tenant.id,
        plan_id=plan.id,
        status="trial",
        monthly_budget_limit=monthly_budget_limit,
        created_by=user.id,
    )
    # repo 的 upsert 不暴露 started_at / expires_at 字段;在这里设置过期日期。
    now = datetime.now(timezone.utc)
    subscription.started_at = now
    subscription.expires_at = now + timedelta(days=trial_days)
    session.flush()

    return tenant
