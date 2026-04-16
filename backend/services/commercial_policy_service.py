"""Thin orchestration layer for commercial control decisions."""
from __future__ import annotations

from typing import Optional

from config import settings
from errors import BudgetExceeded, HighCostActionBlocked, QuotaExceeded
from services import model_routing_service, quota_service, valuation_control_service


def _raise_allowance_error(allowance: dict, *, fallback_action: str) -> None:
    details = {
        "reason": allowance.get("reason"),
        "quota_limit": allowance.get("quota_limit"),
        "quota_used": allowance.get("quota_used"),
        "quota_remaining": allowance.get("quota_remaining"),
        "budget_limit": allowance.get("budget_limit"),
        "projected_budget_used": allowance.get("projected_budget_used"),
        "fallback_action": fallback_action,
    }
    reason = allowance.get("reason")
    if reason == "quota_exceeded":
        raise QuotaExceeded(details=details)
    if reason in {"monthly_budget_exceeded", "single_task_budget_exceeded"}:
        raise BudgetExceeded(details=details)
    raise BudgetExceeded(detail="当前商业化策略不允许执行该请求", details=details)


def _llm_unit_cost(model_name: str) -> float:
    model = (model_name or "").lower()
    if "turbo" in model:
        return settings.llm_turbo_unit_cost
    if "long" in model:
        return settings.llm_long_unit_cost
    return settings.llm_plus_unit_cost


def preflight_vin_valuation(
    session,
    *,
    tenant_id: int,
    single_task_budget: Optional[float] = None,
) -> dict:
    allowance = quota_service.check_allowance(
        session,
        tenant_id=tenant_id,
        resource_type="vin_call",
        requested_quantity=1,
        estimated_internal_cost=settings.che300_basic_unit_cost,
        single_task_budget=single_task_budget,
    )
    if allowance["reason"] == "subscription_missing":
        return {
            "requested_level": "basic",
            "executed_level": "basic",
            "degraded": False,
            "reason": "subscription_missing",
            "allowance": allowance,
            "legacy_mode": True,
        }
    if not allowance["allowed"]:
        _raise_allowance_error(allowance, fallback_action="稍后重试或联系管理员调整额度")
    return {
        "requested_level": "basic",
        "executed_level": "basic",
        "degraded": False,
        "reason": None,
        "allowance": allowance,
    }


def preflight_llm_task(
    session,
    *,
    tenant_id: int,
    task_type: str,
    single_task_budget: Optional[float] = None,
) -> dict:
    route = model_routing_service.resolve_route(
        session, task_type=task_type, tenant_id=tenant_id
    )
    estimated_internal_cost = _llm_unit_cost(route["preferred_model"])
    allowance = quota_service.check_allowance(
        session,
        tenant_id=tenant_id,
        resource_type="ai_report",
        requested_quantity=1,
        estimated_internal_cost=estimated_internal_cost,
        single_task_budget=single_task_budget,
    )
    if allowance["reason"] == "subscription_missing":
        return {
            "route": route,
            "allowance": allowance,
            "use_template_fallback": False,
            "legacy_mode": True,
        }
    if allowance["allowed"]:
        return {"route": route, "allowance": allowance, "use_template_fallback": False}

    fallback_route = dict(route)
    fallback_route["preferred_model"] = route.get("fallback_model") or "qwen-turbo"
    fallback_route["fallback_model"] = "template"
    fallback_allowance = quota_service.check_allowance(
        session,
        tenant_id=tenant_id,
        resource_type="ai_report",
        requested_quantity=1,
        estimated_internal_cost=_llm_unit_cost(fallback_route["preferred_model"]),
        single_task_budget=single_task_budget,
    )
    if fallback_allowance["allowed"]:
        return {
            "route": fallback_route,
            "allowance": fallback_allowance,
            "use_template_fallback": False,
            "degraded": True,
            "reason": allowance["reason"],
        }

    return {
        "route": fallback_route,
        "allowance": fallback_allowance,
        "use_template_fallback": True,
        "degraded": True,
        "reason": allowance["reason"],
    }


def preflight_condition_pricing(
    session,
    *,
    tenant_id: int,
    vehicle_value: Optional[float],
    profit_margin: Optional[float],
    risk_tags: list[str],
    manual_selected: bool,
    approval_mode: bool,
    single_task_budget: Optional[float] = None,
    strict_policy: bool = False,
) -> dict:
    valuation_decision = valuation_control_service.evaluate_request(
        session,
        tenant_id=tenant_id,
        vehicle_value=vehicle_value,
        profit_margin=profit_margin,
        risk_tags=risk_tags,
        manual_selected=manual_selected,
        approval_mode=approval_mode,
    )
    if not valuation_decision["allow_condition_pricing"]:
        if strict_policy:
            raise HighCostActionBlocked(
                details={
                    "reason": valuation_decision["reason"],
                    "matched_rule_types": valuation_decision["matched_rule_types"],
                    "fallback_action": "回退基础VIN估值 + AI解释",
                }
            )
        basic = preflight_vin_valuation(
            session, tenant_id=tenant_id, single_task_budget=single_task_budget
        )
        basic["requested_level"] = "condition_pricing"
        basic["degraded"] = True
        basic["reason"] = valuation_decision["reason"]
        basic["valuation_decision"] = valuation_decision
        return basic

    allowance = quota_service.check_allowance(
        session,
        tenant_id=tenant_id,
        resource_type="condition_pricing",
        requested_quantity=1,
        estimated_internal_cost=settings.che300_condition_pricing_unit_cost,
        single_task_budget=single_task_budget,
    )
    if allowance["reason"] == "subscription_missing":
        if strict_policy:
            _raise_allowance_error(allowance, fallback_action="回退基础VIN估值 + AI解释")
        basic = preflight_vin_valuation(
            session, tenant_id=tenant_id, single_task_budget=single_task_budget
        )
        basic["requested_level"] = "condition_pricing"
        basic["degraded"] = True
        basic["reason"] = "subscription_missing"
        basic["valuation_decision"] = valuation_decision
        return basic
    if not allowance["allowed"]:
        if strict_policy:
            _raise_allowance_error(allowance, fallback_action="回退基础VIN估值 + AI解释")
        basic = preflight_vin_valuation(
            session, tenant_id=tenant_id, single_task_budget=single_task_budget
        )
        basic["requested_level"] = "condition_pricing"
        basic["degraded"] = True
        basic["reason"] = allowance["reason"]
        basic["valuation_decision"] = valuation_decision
        return basic

    return {
        "requested_level": "condition_pricing",
        "executed_level": "condition_pricing",
        "degraded": False,
        "reason": None,
        "valuation_decision": valuation_decision,
        "allowance": allowance,
        "allowed": True,
    }
