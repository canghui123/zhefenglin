from datetime import date

from models.asset import Asset
from services.market_liquidity import calculate_market_liquidity


def test_mainstream_fuel_vehicle_gets_high_liquidity_and_shorter_cycle():
    asset = Asset(
        row_number=2,
        car_description="2021 丰田凯美瑞 2.0G 豪华版",
        first_registration=date(2021, 6, 1),
        loan_principal=120000,
    )

    result = calculate_market_liquidity(
        asset,
        valuation_price=100000,
        base_expected_sale_days=45,
    )

    assert result.energy_type == "fuel"
    assert result.level == "high"
    assert result.score >= 75
    assert result.adjustment > 0
    assert result.expected_sale_days_adjusted < 45
    assert "mainstream_fuel_model" in result.liquidity_risk_tags


def test_cold_new_energy_operating_vehicle_gets_low_liquidity_and_risk_tags():
    asset = Asset(
        row_number=3,
        car_description="2020 威马EX5 纯电 网约 营转非 事故车",
        first_registration=date(2020, 1, 1),
        loan_principal=120000,
        energy_type="bev",
        battery_health_score=70,
        battery_warranty_valid=False,
        operating_vehicle=True,
        ride_hailing_vehicle=True,
        range_km=320,
    )

    result = calculate_market_liquidity(
        asset,
        valuation_price=100000,
        base_expected_sale_days=45,
    )

    assert result.energy_type == "bev"
    assert result.level == "very_low"
    assert result.adjustment == -0.22
    assert result.expected_sale_days_adjusted > 45
    assert "cold_brand_liquidity_risk" in result.new_energy_risk_tags
    assert "battery_health_low" in result.new_energy_risk_tags
    assert "warranty_expired" in result.new_energy_risk_tags
