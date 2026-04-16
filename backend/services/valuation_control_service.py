"""Evaluate whether high-cost condition pricing may be triggered."""
from __future__ import annotations

import json
from typing import Iterable, Optional

from repositories import valuation_rule_repo


def _json_loads(value: Optional[str]) -> dict:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def _matches_rule(
    *,
    trigger_type: str,
    trigger_config: dict,
    vehicle_value: Optional[float],
    profit_margin: Optional[float],
    risk_tags: Iterable[str],
    manual_selected: bool,
    approval_mode: bool,
) -> bool:
    if trigger_type == "profit_margin_threshold":
        if profit_margin is None:
            return False
        lower = float(trigger_config.get("margin_lower_bound", 0))
        upper = float(trigger_config.get("margin_upper_bound", 0))
        return lower <= profit_margin <= upper
    if trigger_type == "high_asset_value":
        if vehicle_value is None:
            return False
        return vehicle_value >= float(trigger_config.get("min_vehicle_value", 0))
    if trigger_type == "high_risk_vehicle":
        rule_tags = set(trigger_config.get("risk_tags", []))
        return bool(rule_tags.intersection(set(risk_tags)))
    if trigger_type == "manual_request":
        return manual_selected and bool(trigger_config.get("requires_manual_selection", True))
    if trigger_type == "approval_report_mode":
        return approval_mode and bool(trigger_config.get("requires_approval_mode", True))
    return False


def evaluate_request(
    session,
    *,
    tenant_id: int,
    vehicle_value: Optional[float],
    profit_margin: Optional[float],
    risk_tags: list[str],
    manual_selected: bool,
    approval_mode: bool,
) -> dict:
    matched_rule_types: list[str] = []
    for rule in valuation_rule_repo.list_active_rules(session, tenant_id=tenant_id):
        if _matches_rule(
            trigger_type=rule.trigger_type,
            trigger_config=_json_loads(rule.trigger_config_json),
            vehicle_value=vehicle_value,
            profit_margin=profit_margin,
            risk_tags=risk_tags,
            manual_selected=manual_selected,
            approval_mode=approval_mode,
        ):
            matched_rule_types.append(rule.trigger_type)

    allowed = bool(matched_rule_types)
    return {
        "allow_condition_pricing": allowed,
        "matched_rule_types": matched_rule_types,
        "fallback_level": "condition_pricing" if allowed else "basic",
        "reason": "rule_match" if allowed else "fallback_to_basic",
    }
