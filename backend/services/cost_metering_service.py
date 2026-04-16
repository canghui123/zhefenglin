"""Usage event recording and monthly cost snapshot aggregation."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from repositories import usage_repo


def _current_month(now: Optional[datetime] = None) -> str:
    current = now or datetime.utcnow()
    return current.strftime("%Y-%m")


def _to_json(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def record_usage(
    session,
    *,
    tenant_id: int,
    user_id: Optional[int],
    module: str,
    action: str,
    resource_type: str,
    quantity: float = 1,
    unit_cost_internal: float = 0,
    unit_price_external: float = 0,
    request_id: Optional[str] = None,
    related_object_type: Optional[str] = None,
    related_object_id: Optional[str] = None,
    metadata=None,
    extra_snapshot_metrics: Optional[dict] = None,
    usage_month: Optional[str] = None,
):
    estimated_cost_total = float(quantity) * float(unit_cost_internal)
    event = usage_repo.create_usage_event(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        module=module,
        action=action,
        resource_type=resource_type,
        quantity=float(quantity),
        unit_cost_internal=float(unit_cost_internal),
        unit_price_external=float(unit_price_external),
        estimated_cost_total=estimated_cost_total,
        request_id=request_id,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        metadata_json=_to_json(metadata),
    )

    month = usage_month or _current_month()
    snapshot = usage_repo.get_cost_snapshot(session, tenant_id=tenant_id, month=month)
    if snapshot is None:
        snapshot = usage_repo.create_cost_snapshot(session, tenant_id=tenant_id, month=month)

    metrics = extra_snapshot_metrics or {}

    if resource_type == "vin_call":
        snapshot.vin_calls += int(quantity)
        snapshot.che300_cost += estimated_cost_total
    elif resource_type == "condition_pricing":
        snapshot.condition_pricing_calls += int(quantity)
        snapshot.che300_cost += estimated_cost_total
    elif resource_type == "llm_completion":
        snapshot.llm_cost += float(metrics.get("llm_cost", estimated_cost_total))

    snapshot.llm_input_tokens += int(metrics.get("llm_input_tokens", 0))
    snapshot.llm_output_tokens += int(metrics.get("llm_output_tokens", 0))
    if resource_type != "llm_completion":
        snapshot.llm_cost += float(metrics.get("llm_cost", 0))
    snapshot.estimated_revenue += float(metrics.get("estimated_revenue", 0))
    snapshot.total_cost = float(snapshot.che300_cost) + float(snapshot.llm_cost)
    snapshot.estimated_gross_profit = (
        float(snapshot.estimated_revenue) - float(snapshot.total_cost)
    )
    session.flush()
    return event
