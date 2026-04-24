from services.portfolio_engine import compute_cashflow_projection


def test_cashflow_projection_returns_monotonic_scenario_band():
    segments = [
        {
            "segment_name": "M3(61-90天) | 已入库",
            "recommended_strategy": "retail_auction",
            "total_ead": 1_000_000,
            "asset_count": 10,
        }
    ]

    result = compute_cashflow_projection(segments)

    for bucket in result["total_buckets"]:
        assert bucket["pessimistic_net_cash_flow"] <= bucket["neutral_net_cash_flow"]
        assert bucket["neutral_net_cash_flow"] <= bucket["optimistic_net_cash_flow"]
        assert bucket["net_cash_flow"] == bucket["neutral_net_cash_flow"]

    for strategy in result["by_strategy"]:
        for bucket in strategy["buckets"]:
            assert bucket["pessimistic_net_cash_flow"] <= bucket["neutral_net_cash_flow"]
            assert bucket["neutral_net_cash_flow"] <= bucket["optimistic_net_cash_flow"]
