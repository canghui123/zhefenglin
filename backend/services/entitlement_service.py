"""Runtime enforcement for tenant subscriptions, seats, and feature access."""
from __future__ import annotations

import json
from typing import Any, Iterable, Optional

from sqlalchemy import func, select

from db.models.membership import Membership
from errors import FeatureNotEnabled, SeatLimitExceeded
from repositories import plan_repo, subscription_repo
from services.feature_catalog import FEATURE_KEYS


def _load_subscription_plan(session, *, tenant_id: int):
    subscription = subscription_repo.get_current_subscription(session, tenant_id=tenant_id)
    if subscription is None:
        return None, None
    plan = plan_repo.get_plan_by_id(session, subscription.plan_id)
    return subscription, plan


def _parse_feature_flags(raw: Optional[str]) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def count_occupied_seats(session, *, tenant_id: int) -> int:
    stmt = (
        select(func.count())
        .select_from(Membership)
        .where(Membership.tenant_id == tenant_id)
    )
    return int(session.scalar(stmt) or 0)


def ensure_seat_available(session, *, tenant_id: int) -> dict[str, Any]:
    subscription, plan = _load_subscription_plan(session, tenant_id=tenant_id)
    if subscription is None or plan is None:
        return {
            "enforced": False,
            "tenant_id": tenant_id,
            "seat_limit": None,
            "occupied_seats": count_occupied_seats(session, tenant_id=tenant_id),
            "plan_code": None,
        }

    seat_limit = int(plan.seat_limit or 0)
    occupied_seats = count_occupied_seats(session, tenant_id=tenant_id)
    details = {
        "tenant_id": tenant_id,
        "seat_limit": seat_limit,
        "occupied_seats": occupied_seats,
        "plan_code": plan.code,
        "plan_name": plan.name,
    }
    if occupied_seats >= seat_limit:
        raise SeatLimitExceeded(details=details)
    return {"enforced": True, **details}


def get_effective_feature(session, *, tenant_id: int, feature_key: str) -> dict[str, Any]:
    subscription, plan = _load_subscription_plan(session, tenant_id=tenant_id)
    if subscription is None:
        return {
            "enabled": True,
            "feature_key": feature_key,
            "tenant_id": tenant_id,
            "source": "legacy",
            "plan_code": None,
            "plan_name": None,
        }

    tenant_override = subscription_repo.get_feature_entitlement(
        session,
        feature_key=feature_key,
        tenant_id=tenant_id,
    )
    if tenant_override is not None:
        return {
            "enabled": bool(tenant_override.is_enabled),
            "feature_key": feature_key,
            "tenant_id": tenant_id,
            "source": "tenant",
            "plan_code": plan.code if plan is not None else None,
            "plan_name": plan.name if plan is not None else None,
        }

    if plan is not None:
        plan_entitlement = subscription_repo.get_feature_entitlement(
            session,
            feature_key=feature_key,
            plan_id=plan.id,
        )
        if plan_entitlement is not None:
            return {
                "enabled": bool(plan_entitlement.is_enabled),
                "feature_key": feature_key,
                "tenant_id": tenant_id,
                "source": "plan",
                "plan_code": plan.code,
                "plan_name": plan.name,
            }

        plan_flags = _parse_feature_flags(plan.feature_flags_json)
        if feature_key in plan_flags:
            return {
                "enabled": bool(plan_flags[feature_key]),
                "feature_key": feature_key,
                "tenant_id": tenant_id,
                "source": "plan_flags",
                "plan_code": plan.code,
                "plan_name": plan.name,
            }

    return {
        "enabled": False,
        "feature_key": feature_key,
        "tenant_id": tenant_id,
        "source": "missing",
        "plan_code": plan.code if plan is not None else None,
        "plan_name": plan.name if plan is not None else None,
    }


def ensure_feature_enabled(session, *, tenant_id: int, feature_key: str) -> dict[str, Any]:
    result = get_effective_feature(session, tenant_id=tenant_id, feature_key=feature_key)
    if result["enabled"]:
        return result

    detail = "当前套餐未开通该功能"
    if result["source"] == "tenant":
        detail = "当前租户策略已关闭该功能"

    raise FeatureNotEnabled(detail=detail, details=result)


def build_feature_capabilities(
    session,
    *,
    tenant_id: Optional[int],
    feature_keys: Optional[Iterable[str]] = None,
) -> dict[str, bool]:
    keys = tuple(feature_keys or FEATURE_KEYS)
    if tenant_id is None:
        return {key: True for key in keys}
    return {
        key: bool(get_effective_feature(session, tenant_id=tenant_id, feature_key=key)["enabled"])
        for key in keys
    }
