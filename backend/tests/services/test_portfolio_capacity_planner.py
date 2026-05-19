from models.portfolio import PortfolioCapacitySettings
from services.portfolio_capacity_planner import build_capacity_plan
from services.portfolio_engine import generate_mock_portfolio


def test_capacity_plan_never_exceeds_budget_or_resource_limits():
    data = generate_mock_portfolio()
    settings = PortfolioCapacitySettings(
        monthly_towing_capacity=8,
        monthly_litigation_capacity=10,
        monthly_auction_capacity=12,
        monthly_collection_capacity=15,
        inventory_yard_capacity=12,
        monthly_disposal_budget=800000,
        legal_team_capacity=10,
        external_vendor_capacity=12,
    )

    plan = build_capacity_plan(data["segments"], settings)

    assert plan.next_month_deferred_pool
    assert plan.resource_usage["towing_tasks"] <= settings.monthly_towing_capacity
    assert plan.resource_usage["litigation_cases"] <= settings.monthly_litigation_capacity
    assert plan.resource_usage["auction_units"] <= settings.monthly_auction_capacity
    assert plan.resource_usage["collection_accounts"] <= settings.monthly_collection_capacity
    assert plan.resource_usage["inventory_units"] <= settings.inventory_yard_capacity
    assert plan.resource_usage["legal_team_cases"] <= settings.legal_team_capacity
    assert plan.resource_usage["external_vendor_units"] <= settings.external_vendor_capacity
    assert sum(item.required_cost for item in plan.current_month_execution_plan) <= settings.monthly_disposal_budget
    assert plan.capacity_bottlenecks


def test_capacity_plan_pauses_hard_blocked_segments():
    segments = [
        {
            "segment_name": "M4(91-120天) | 未收回",
            "overdue_bucket": "M4(91-120天)",
            "recovered_status": "未收回",
            "asset_count": 10,
            "total_ead": 1_000_000,
            "avg_vehicle_value": 80000,
            "avg_lgd": 0.55,
            "avg_recovery_days": 120,
            "expected_loss_amount": 550000,
            "expected_loss_rate": 0.55,
            "cash_30d": 30000,
            "cash_90d": 200000,
            "cash_180d": 450000,
            "recommended_strategy": "retail_auction",
        }
    ]

    plan = build_capacity_plan(segments, PortfolioCapacitySettings(monthly_disposal_budget=5_000_000))

    assert not plan.current_month_execution_plan
    assert plan.paused_pool
    assert plan.paused_pool[0].status == "paused"
    assert "硬约束" in plan.paused_pool[0].reason
