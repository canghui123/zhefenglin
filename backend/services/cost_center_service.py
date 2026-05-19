"""Aggregations used by admin cost-center endpoints."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from repositories import (
    approval_repo,
    plan_repo,
    subscription_repo,
    tenant_repo,
    usage_repo,
    work_order_repo,
)


def _current_month(now: datetime = None) -> str:
    current = now or datetime.utcnow()
    return current.strftime("%Y-%m")


def build_overview(session) -> dict:
    month = _current_month()
    snapshots = usage_repo.list_cost_snapshots(session, month=month)
    monthly_subscriptions = subscription_repo.list_current_subscriptions(session)

    totals = {
        "vin_calls": 0,
        "condition_pricing_calls": 0,
        "llm_input_tokens": 0,
        "llm_output_tokens": 0,
        "llm_cost": 0.0,
        "che300_cost": 0.0,
        "total_cost": 0.0,
        "estimated_revenue": 0.0,
        "estimated_gross_profit": 0.0,
    }
    for row in snapshots:
        totals["vin_calls"] += row.vin_calls
        totals["condition_pricing_calls"] += row.condition_pricing_calls
        totals["llm_input_tokens"] += row.llm_input_tokens
        totals["llm_output_tokens"] += row.llm_output_tokens
        totals["llm_cost"] += float(row.llm_cost)
        totals["che300_cost"] += float(row.che300_cost)
        totals["total_cost"] += float(row.total_cost)
        totals["estimated_revenue"] += float(row.estimated_revenue)
        totals["estimated_gross_profit"] += float(row.estimated_gross_profit)

    tenant_rows = build_tenant_breakdown(session)
    module_rows = {}
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1)

    for tenant in tenant_repo.list_tenants(session):
        for event in usage_repo.list_usage_events_for_period(
            session,
            tenant_id=tenant.id,
            start_at=month_start,
            end_at=month_end,
        ):
            row = module_rows.setdefault(
                event.module,
                {"module": event.module, "events": 0, "quantity": 0.0, "cost": 0.0},
            )
            row["events"] += 1
            row["quantity"] += float(event.quantity)
            row["cost"] += float(event.estimated_cost_total)

    return {
        "month": month,
        "totals": totals,
        "tenant_count": len(tenant_rows),
        "active_subscription_count": len(monthly_subscriptions),
        "modules": list(module_rows.values()),
    }


def build_tenant_breakdown(session) -> list[dict]:
    month = _current_month()
    snapshots = {row.tenant_id: row for row in usage_repo.list_cost_snapshots(session, month=month)}
    subscriptions = {
        row.tenant_id: row for row in subscription_repo.list_current_subscriptions(session)
    }
    plans = {plan.id: plan for plan in plan_repo.list_plans(session)}

    rows = []
    for tenant in tenant_repo.list_tenants(session):
        snapshot = snapshots.get(tenant.id)
        subscription = subscriptions.get(tenant.id)
        plan = plans.get(subscription.plan_id) if subscription is not None else None
        total_cost = float(snapshot.total_cost) if snapshot is not None else 0.0
        vin_calls = int(snapshot.vin_calls) if snapshot is not None else 0
        condition_calls = int(snapshot.condition_pricing_calls) if snapshot is not None else 0
        estimated_revenue = float(snapshot.estimated_revenue) if snapshot is not None else 0.0
        if estimated_revenue == 0 and plan is not None:
            estimated_revenue = float(plan.monthly_price)
        rows.append(
            {
                "tenant_id": tenant.id,
                "tenant_code": tenant.code,
                "tenant_name": tenant.name,
                "plan_code": plan.code if plan is not None else None,
                "plan_name": plan.name if plan is not None else None,
                "vin_calls": vin_calls,
                "condition_pricing_calls": condition_calls,
                "llm_input_tokens": int(snapshot.llm_input_tokens) if snapshot is not None else 0,
                "llm_output_tokens": int(snapshot.llm_output_tokens) if snapshot is not None else 0,
                "total_cost": total_cost,
                "estimated_revenue": estimated_revenue,
                "estimated_gross_profit": (
                    float(snapshot.estimated_gross_profit)
                    if snapshot is not None
                    else estimated_revenue - total_cost
                ),
                "avg_cost_per_vehicle": (
                    round(total_cost / max(vin_calls + condition_calls, 1), 2)
                    if total_cost
                    else 0
                ),
                "monthly_budget_limit": (
                    float(subscription.monthly_budget_limit) if subscription is not None else 0
                ),
            }
        )
    return rows


def export_tenant_breakdown_csv(session) -> str:
    rows = build_tenant_breakdown(session)
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "tenant_id",
            "tenant_code",
            "tenant_name",
            "plan_code",
            "plan_name",
            "vin_calls",
            "condition_pricing_calls",
            "llm_input_tokens",
            "llm_output_tokens",
            "total_cost",
            "estimated_revenue",
            "estimated_gross_profit",
            "avg_cost_per_vehicle",
            "monthly_budget_limit",
        ],
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def build_value_dashboard(session) -> dict:
    month = _current_month()
    snapshots = usage_repo.list_cost_snapshots(session, month=month)
    vin_calls = sum(row.vin_calls for row in snapshots)
    condition_calls = sum(row.condition_pricing_calls for row in snapshots)

    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1)

    ai_report_calls = 0
    blocked_high_cost_calls = 0
    sandbox_runs = 0
    asset_package_uploads = 0
    for tenant in tenant_repo.list_tenants(session):
        for event in usage_repo.list_usage_events_for_period(
            session,
            tenant_id=tenant.id,
            start_at=month_start,
            end_at=month_end,
        ):
            if event.resource_type == "ai_report":
                ai_report_calls += int(event.quantity)
            if event.resource_type == "sandbox_run":
                sandbox_runs += int(event.quantity)
            if event.resource_type == "asset_package_upload":
                asset_package_uploads += int(event.quantity)
            metadata = {}
            try:
                metadata = json.loads(event.metadata_json or "{}")
            except json.JSONDecodeError:
                metadata = {}
            if metadata.get("degraded") or metadata.get("template_fallback"):
                blocked_high_cost_calls += 1

    approval_rows = approval_repo.list_requests(session)
    high_risk_vehicles = sum(
        1 for row in approval_rows if row.type == "condition_pricing"
    ) + condition_calls
    estimated_decisions_processed = vin_calls + condition_calls + sandbox_runs
    estimated_hours_saved = round(
        vin_calls * 0.12
        + ai_report_calls * 0.25
        + sandbox_runs * 0.2
        + asset_package_uploads * 1.5,
        1,
    )
    recommended_path_coverage = round(
        min(100.0, ((condition_calls + ai_report_calls) / max(estimated_decisions_processed, 1)) * 100),
        1,
    )
    tenant_value_rows = []
    total_tasks = 0
    done_tasks = 0
    accelerated_cash_in = 0.0
    estimated_extra_recovery = 0.0
    auction_price_improvement = 0.0

    for tenant in tenant_repo.list_tenants(session):
        tenant_tasks = work_order_repo.list_work_orders_for_tenant(session, tenant_id=tenant.id)
        tenant_done = [task for task in tenant_tasks if task.status == "done"]
        tenant_expected = 0.0
        tenant_actual = 0.0
        for task in tenant_tasks:
            payload = json.loads(task.payload_json or "{}")
            result = json.loads(task.result_json or "{}")
            expected = float(payload.get("expected_recovery") or 0)
            actual = float(result.get("actual_recovery") or 0)
            tenant_expected += expected
            tenant_actual += actual
            if task.status == "done":
                accelerated_cash_in += actual
                uplift = max(actual - expected, 0)
                estimated_extra_recovery += uplift if actual else expected * 0.05
                if task.order_type == "auction":
                    auction_price_improvement += uplift
        total_tasks += len(tenant_tasks)
        done_tasks += len(tenant_done)
        tenant_value_rows.append(
            {
                "tenant_id": tenant.id,
                "tenant_code": tenant.code,
                "tenant_name": tenant.name,
                "task_count": len(tenant_tasks),
                "completed_task_count": len(tenant_done),
                "expected_recovery": round(tenant_expected, 2),
                "actual_recovery": round(tenant_actual, 2),
                "estimated_extra_recovery": round(max(tenant_actual - tenant_expected, 0), 2),
            }
        )

    manual_valuation_cost_saved = round(vin_calls * 30 + condition_calls * 120, 2)
    avoided_loss_amount = round(high_risk_vehicles * 3000 + blocked_high_cost_calls * 800, 2)
    task_completion_rate = round(done_tasks / total_tasks * 100, 1) if total_tasks else 0
    summary_text = (
        f"本月系统处理决策{estimated_decisions_processed}次，生成报告{ai_report_calls}份，"
        f"预计节省人工{estimated_hours_saved}小时，识别高风险资产{high_risk_vehicles}台，"
        f"估计避免损失{avoided_loss_amount:,.0f}元，任务闭环提前回款{accelerated_cash_in:,.0f}元。"
    )
    return {
        "month": month,
        "estimated_hours_saved": estimated_hours_saved,
        "high_risk_vehicles": high_risk_vehicles,
        "blocked_high_cost_calls": blocked_high_cost_calls,
        "recommended_path_coverage": recommended_path_coverage,
        "estimated_decisions_processed": estimated_decisions_processed,
        "estimated_extra_recovery": round(estimated_extra_recovery, 2),
        "avoided_loss_amount": avoided_loss_amount,
        "accelerated_cash_in": round(accelerated_cash_in, 2),
        "manual_valuation_cost_saved": manual_valuation_cost_saved,
        "auction_price_improvement": round(auction_price_improvement, 2),
        "bad_asset_identification_count": high_risk_vehicles,
        "reports_generated": ai_report_calls,
        "hours_saved": estimated_hours_saved,
        "task_completion_rate": task_completion_rate,
        "tenant_value_rows": tenant_value_rows,
        "customer_summary": summary_text,
        "source_trace": {
            "vin_calls": vin_calls,
            "condition_pricing_calls": condition_calls,
            "ai_report_calls": ai_report_calls,
            "sandbox_runs": sandbox_runs,
            "asset_package_uploads": asset_package_uploads,
            "task_count": total_tasks,
            "completed_task_count": done_tasks,
        },
    }
