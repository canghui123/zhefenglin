from models.asset import Asset, PricingParameters
from models.valuation import ValuationResult
from services.pricing_engine import calculate_single_asset


def _valuation(value: float) -> ValuationResult:
    return ValuationResult(
        model_id="mock_1",
        model_name="mock",
        medium_price=value,
        is_mock=True,
    )


def test_region_coefficient_affects_towing_cost_and_revenue():
    params = PricingParameters(towing_cost=1000, daily_parking=20, disposal_period=45)
    base_asset = Asset(
        row_number=2,
        car_description="2021 丰田 凯美瑞",
        buyout_price=80_000,
    )
    slow_region_asset = Asset(
        row_number=2,
        car_description="2021 丰田 凯美瑞",
        buyout_price=80_000,
        province="四川省",
        city="成都市",
    )

    base = calculate_single_asset(base_asset, params, _valuation(120_000), None)
    slow_region = calculate_single_asset(
        slow_region_asset,
        params,
        _valuation(120_000),
        None,
    )

    assert slow_region.towing_cost > base.towing_cost
    assert slow_region.expected_revenue < base.expected_revenue
    assert slow_region.region_code == "SC"


def test_new_energy_asset_gets_residual_value_risk_flag():
    result = calculate_single_asset(
        Asset(
            row_number=2,
            car_description="2022 比亚迪 汉EV",
            buyout_price=120_000,
        ),
        PricingParameters(),
        _valuation(180_000),
        None,
    )

    assert any("新能源" in flag for flag in result.risk_flags)
    assert result.depreciation_rate is not None
