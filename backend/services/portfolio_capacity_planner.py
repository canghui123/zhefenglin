"""Resource-constrained portfolio execution planning.

This is intentionally a deterministic heuristic rather than a black-box linear
program: candidates are ranked by incremental recovery per cost, cash speed and
feasibility, then selected until monthly capacity or budget is exhausted.
"""

from __future__ import annotations

from math import floor
from typing import Optional

from sqlalchemy.orm import Session

from models.portfolio import (
    CapacityPlanItem,
    PortfolioCapacityPlan,
    PortfolioCapacitySettings,
)
from repositories import portfolio_capacity_settings_repo
from services.portfolio_engine import STRATEGY_TYPES, compute_strategy_comparison


RESOURCE_LIMIT_FIELDS = {
    "towing_tasks": "monthly_towing_capacity",
    "litigation_cases": "monthly_litigation_capacity",
    "auction_units": "monthly_auction_capacity",
    "collection_accounts": "monthly_collection_capacity",
    "inventory_units": "inventory_yard_capacity",
    "legal_team_cases": "legal_team_capacity",
    "external_vendor_units": "external_vendor_capacity",
}

STRATEGY_TO_TASK = {
    "collection": "collection",
    "restructure": "restructure",
    "retail_auction": "auction",
    "litigation": "litigation",
    "special_procedure": "special_procedure",
    "debt_transfer": "debt_transfer",
    "vehicle_transfer": "auction",
    "bulk_clearance": "auction",
}

HARD_BLOCK_KEYWORDS = ("无法", "不可用", "需已入库", "车辆未收回")

def get_capacity_settings(
    session: Session,
    tenant_id: Optional[int],
) -> PortfolioCapacitySettings:
    row = portfolio_capacity_settings_repo.get_capacity_settings_row(
        session,
        tenant_id=tenant_id,
    )
    if row is None:
        return PortfolioCapacitySettings()
    return portfolio_capacity_settings_repo.to_settings(row)


def update_capacity_settings(
    session: Session,
    tenant_id: Optional[int],
    settings: PortfolioCapacitySettings,
    *,
    updated_by: Optional[int],
) -> PortfolioCapacitySettings:
    row = portfolio_capacity_settings_repo.upsert_capacity_settings(
        session,
        tenant_id=tenant_id,
        settings=settings,
        updated_by=updated_by,
    )
    return portfolio_capacity_settings_repo.to_settings(row)


def _strategy_for_segment(segment: dict) -> dict:
    strategies = compute_strategy_comparison(segment)
    preferred = segment.get("recommended_strategy")
    if preferred:
        for row in strategies:
            if row["strategy_type"] == preferred:
                return row
    feasible = [row for row in strategies if not _has_hard_block(row)]
    return feasible[0] if feasible else strategies[0]


def _collection_baseline(segment: dict) -> float:
    for row in compute_strategy_comparison(segment):
        if row["strategy_type"] == "collection":
            return float(row["net_recovery_pv"])
    return 0.0


def _has_hard_block(strategy: dict) -> bool:
    reasons = "；".join(strategy.get("not_recommended_reasons") or [])
    return any(keyword in reasons for keyword in HARD_BLOCK_KEYWORDS)


def _resource_needs(strategy_type: str, segment: dict) -> dict[str, float]:
    count = int(segment.get("asset_count") or 0)
    status = segment.get("recovered_status", "")
    needs = {key: 0.0 for key in RESOURCE_LIMIT_FIELDS}

    if strategy_type in {"collection", "restructure"}:
        needs["collection_accounts"] = count
    if strategy_type in {"retail_auction", "vehicle_transfer", "bulk_clearance"}:
        needs["auction_units"] = count
        needs["external_vendor_units"] = count
        needs["inventory_units"] = count
        if status != "已入库":
            needs["towing_tasks"] = count
    if strategy_type == "litigation":
        needs["litigation_cases"] = count
        needs["legal_team_cases"] = count
    if strategy_type == "special_procedure":
        needs["litigation_cases"] = count
        needs["legal_team_cases"] = count
        needs["auction_units"] = count
    if strategy_type == "debt_transfer":
        needs["external_vendor_units"] = count

    return needs


def _feasibility(strategy: dict) -> float:
    probability = float(strategy.get("success_probability") or 0)
    penalties = 0.12 * len(strategy.get("not_recommended_reasons") or [])
    return max(0.0, min(1.0, probability - penalties))


def _candidate(segment: dict) -> dict:
    strategy = _strategy_for_segment(segment)
    asset_count = int(segment.get("asset_count") or 0)
    cost = float(strategy.get("total_cost") or 0)
    net = float(strategy.get("net_recovery_pv") or 0)
    baseline = _collection_baseline(segment)
    incremental = max(0.0, net - baseline)
    days = max(int(strategy.get("expected_recovery_days") or 1), 1)
    feasibility = _feasibility(strategy)
    needs = _resource_needs(strategy["strategy_type"], segment)
    return {
        "segment": segment,
        "strategy": strategy,
        "asset_count": asset_count,
        "required_cost": cost,
        "expected_net_recovery": net,
        "expected_incremental_recovery": incremental,
        "cash_return_speed": round(1 / days, 6),
        "execution_feasibility": feasibility,
        "resource_needs": needs,
        "hard_blocked": _has_hard_block(strategy),
    }


def _rank_key(candidate: dict) -> tuple[float, float, float]:
    cost = max(float(candidate["required_cost"]), 1.0)
    return (
        candidate["expected_incremental_recovery"] / cost,
        candidate["cash_return_speed"],
        candidate["execution_feasibility"],
    )


def _make_item(
    candidate: dict,
    *,
    selected_count: int,
    deferred_count: int,
    status: str,
    reason: str = "",
) -> CapacityPlanItem:
    asset_count = max(candidate["asset_count"], 1)
    scale = selected_count / asset_count if status == "selected" else deferred_count / asset_count
    strategy = candidate["strategy"]
    return CapacityPlanItem(
        segment_name=candidate["segment"]["segment_name"],
        strategy_type=strategy["strategy_type"],
        strategy_name=STRATEGY_TYPES.get(strategy["strategy_type"], strategy["strategy_type"]),
        task_type=STRATEGY_TO_TASK.get(strategy["strategy_type"], strategy["strategy_type"]),
        asset_count=candidate["asset_count"],
        selected_count=selected_count,
        deferred_count=deferred_count,
        expected_net_recovery=round(candidate["expected_net_recovery"] * scale, 2),
        expected_incremental_recovery=round(candidate["expected_incremental_recovery"] * scale, 2),
        required_cost=round(candidate["required_cost"] * scale, 2),
        cash_return_speed=candidate["cash_return_speed"],
        execution_feasibility=round(candidate["execution_feasibility"], 4),
        resource_needs={
            key: round(value * scale, 2)
            for key, value in candidate["resource_needs"].items()
            if value > 0
        },
        status=status,
        reason=reason,
    )


def _capacity_reason(candidate: dict, remaining: dict[str, float], budget_remaining: float) -> str:
    reasons: list[str] = []
    asset_count = max(candidate["asset_count"], 1)
    for key, total_need in candidate["resource_needs"].items():
        per_unit = total_need / asset_count
        if per_unit > 0 and remaining.get(key, 0) < per_unit:
            reasons.append(f"{key}不足")
    cost_per_unit = candidate["required_cost"] / asset_count
    if cost_per_unit > 0 and budget_remaining < cost_per_unit:
        reasons.append("monthly_disposal_budget不足")
    return "、".join(reasons) or "综合产能不足"


def build_capacity_plan(
    segments: list[dict],
    settings: Optional[PortfolioCapacitySettings] = None,
) -> PortfolioCapacityPlan:
    settings = settings or PortfolioCapacitySettings()
    candidates = [_candidate(segment) for segment in segments if int(segment.get("asset_count") or 0) > 0]
    candidates.sort(key=_rank_key, reverse=True)

    remaining = {
        key: float(getattr(settings, field))
        for key, field in RESOURCE_LIMIT_FIELDS.items()
    }
    budget_remaining = float(settings.monthly_disposal_budget)
    current: list[CapacityPlanItem] = []
    deferred: list[CapacityPlanItem] = []
    paused: list[CapacityPlanItem] = []
    bottlenecks: list[str] = []
    budget_gap = 0.0
    capacity_added_value = 0.0

    for candidate in candidates:
        if candidate["hard_blocked"]:
            paused.append(
                _make_item(
                    candidate,
                    selected_count=0,
                    deferred_count=candidate["asset_count"],
                    status="paused",
                    reason="存在硬约束，需先解除物权、入库或路径可行性问题",
                )
            )
            continue

        asset_count = max(candidate["asset_count"], 1)
        max_units = candidate["asset_count"]
        for key, total_need in candidate["resource_needs"].items():
            per_unit = total_need / asset_count
            if per_unit > 0:
                max_units = min(max_units, int(floor(remaining.get(key, 0) / per_unit)))
        cost_per_unit = candidate["required_cost"] / asset_count
        if cost_per_unit > 0:
            max_units = min(max_units, int(floor(budget_remaining / cost_per_unit)))

        if max_units <= 0:
            reason = _capacity_reason(candidate, remaining, budget_remaining)
            bottlenecks.extend(part for part in reason.split("、") if part)
            deferred.append(
                _make_item(
                    candidate,
                    selected_count=0,
                    deferred_count=candidate["asset_count"],
                    status="deferred",
                    reason=reason,
                )
            )
            budget_gap += candidate["required_cost"]
            capacity_added_value += candidate["expected_incremental_recovery"]
            continue

        selected = min(candidate["asset_count"], max_units)
        for key, total_need in candidate["resource_needs"].items():
            remaining[key] -= total_need * selected / asset_count
        budget_remaining -= candidate["required_cost"] * selected / asset_count

        current.append(
            _make_item(
                candidate,
                selected_count=selected,
                deferred_count=max(candidate["asset_count"] - selected, 0),
                status="selected",
            )
        )

        deferred_count = candidate["asset_count"] - selected
        if deferred_count > 0:
            reason = _capacity_reason(candidate, remaining, budget_remaining)
            bottlenecks.extend(part for part in reason.split("、") if part)
            deferred.append(
                _make_item(
                    candidate,
                    selected_count=0,
                    deferred_count=deferred_count,
                    status="deferred",
                    reason=reason,
                )
            )
            budget_gap += candidate["required_cost"] * deferred_count / asset_count
            capacity_added_value += candidate["expected_incremental_recovery"] * deferred_count / asset_count

    resource_usage = {
        key: round(float(getattr(settings, field)) - remaining[key], 2)
        for key, field in RESOURCE_LIMIT_FIELDS.items()
    }
    remaining_capacity = {key: round(max(value, 0), 2) for key, value in remaining.items()}
    selected_assets = sum(item.selected_count for item in current)
    total_net = sum(item.expected_net_recovery for item in current)
    total_incremental = sum(item.expected_incremental_recovery for item in current)
    bottleneck_list = list(dict.fromkeys(bottlenecks))

    summary = (
        f"本月建议优先处理{selected_assets}台资产，预计净回收{round(total_net / 10000, 2)}万元；"
        f"剩余{sum(item.deferred_count for item in deferred)}台递延，主要瓶颈："
        f"{'、'.join(bottleneck_list) if bottleneck_list else '暂无'}。"
    )

    return PortfolioCapacityPlan(
        settings=settings,
        current_month_execution_plan=current,
        next_month_deferred_pool=deferred,
        paused_pool=paused,
        capacity_bottlenecks=bottleneck_list,
        budget_gap=round(budget_gap, 2),
        incremental_recovery_if_capacity_added=round(capacity_added_value, 2),
        resource_usage=resource_usage,
        remaining_capacity=remaining_capacity,
        total_selected_assets=selected_assets,
        total_expected_net_recovery=round(total_net, 2),
        total_expected_incremental_recovery=round(total_incremental, 2),
        summary=summary,
    )
