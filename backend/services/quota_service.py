"""Quota and budget checks for commercialized features."""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

from repositories import plan_repo, subscription_repo, usage_repo


RESOURCE_QUOTA_FIELDS = {
    "vin_call": "included_vin_calls",
    "condition_pricing": "included_condition_pricing_points",
    "ai_report": "included_ai_reports",
    "asset_package_upload": "included_asset_packages",
    "sandbox_run": "included_sandbox_runs",
    "seat": "seat_limit",
}


def _month_bounds(now: Optional[datetime] = None) -> Tuple[datetime, datetime]:
    current = now or datetime.utcnow()
    start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def check_allowance(
    session,
    *,
    tenant_id: int,
    resource_type: str,
    requested_quantity: float = 1,
    estimated_internal_cost: float = 0,
    single_task_budget: Optional[float] = None,
) -> dict:
    subscription = subscription_repo.get_current_subscription(session, tenant_id=tenant_id)
    if subscription is None:
        return {
            "allowed": False,
            "reason": "subscription_missing",
            "quota_limit": 0,
            "quota_used": 0,
            "quota_remaining": 0,
            "budget_limit": 0,
            "projected_budget_used": 0,
        }

    plan = plan_repo.get_plan_by_id(session, subscription.plan_id)
    quota_field = RESOURCE_QUOTA_FIELDS.get(resource_type)
    quota_limit = int(getattr(plan, quota_field, 0)) if plan is not None and quota_field else 0

    month_start, month_end = _month_bounds()
    usage_events = usage_repo.list_usage_events_for_period(
        session,
        tenant_id=tenant_id,
        start_at=month_start,
        end_at=month_end,
        resource_type=resource_type,
    )
    quota_used = sum(float(event.quantity) for event in usage_events)
    quota_remaining = max(quota_limit - quota_used, 0)

    monthly_events = usage_repo.list_usage_events_for_period(
        session,
        tenant_id=tenant_id,
        start_at=month_start,
        end_at=month_end,
    )
    monthly_cost_used = sum(float(event.estimated_cost_total) for event in monthly_events)
    projected_budget_used = monthly_cost_used + estimated_internal_cost

    if single_task_budget is not None and estimated_internal_cost > single_task_budget:
        return {
            "allowed": False,
            "reason": "single_task_budget_exceeded",
            "quota_limit": quota_limit,
            "quota_used": quota_used,
            "quota_remaining": quota_remaining,
            "budget_limit": subscription.monthly_budget_limit,
            "projected_budget_used": projected_budget_used,
        }

    if quota_field is not None and quota_limit >= 0 and quota_used + requested_quantity > quota_limit:
        return {
            "allowed": False,
            "reason": "quota_exceeded",
            "quota_limit": quota_limit,
            "quota_used": quota_used,
            "quota_remaining": quota_remaining,
            "budget_limit": subscription.monthly_budget_limit,
            "projected_budget_used": projected_budget_used,
        }

    budget_limit = float(subscription.monthly_budget_limit or 0)
    if budget_limit > 0 and projected_budget_used > budget_limit:
        return {
            "allowed": False,
            "reason": "monthly_budget_exceeded",
            "quota_limit": quota_limit,
            "quota_used": quota_used,
            "quota_remaining": quota_remaining,
            "budget_limit": budget_limit,
            "projected_budget_used": projected_budget_used,
        }

    return {
        "allowed": True,
        "reason": None,
        "quota_limit": quota_limit,
        "quota_used": quota_used,
        "quota_remaining": quota_remaining,
        "budget_limit": budget_limit,
        "projected_budget_used": projected_budget_used,
    }
