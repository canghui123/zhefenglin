from models.simulation import SandboxInput
from services.sandbox_simulator import run_simulation


def _input(**overrides) -> SandboxInput:
    data = {
        "car_description": "2021 丰田 凯美瑞 2.0G",
        "entry_date": "2026-04-01",
        "overdue_bucket": "M3(61-90天)",
        "overdue_amount": 120000,
        "che300_value": 150000,
        "vehicle_type": "japanese",
        "vehicle_age_years": 5,
        "daily_parking": 20,
        "recovery_cost": 2000,
        "vehicle_recovered": True,
        "vehicle_in_inventory": True,
    }
    data.update(overrides)
    return SandboxInput(**data)


def test_special_procedure_blocked_before_m3_even_when_in_inventory():
    result = run_simulation(_input(overdue_bucket="M2(31-60天)"))

    assert result.path_d.available is False
    assert "M3" in result.path_d.unavailable_reason
    assert result.best_path != "D"
    assert "推荐【实现担保物权特别程序】" not in result.recommendation


def test_special_procedure_blocked_when_vehicle_not_recovered():
    result = run_simulation(
        _input(
            overdue_bucket="M4(91-120天)",
            vehicle_recovered=False,
            vehicle_in_inventory=True,
        )
    )

    assert result.input.vehicle_in_inventory is False
    assert result.path_d.available is False
    assert "尚未收回" in result.path_d.unavailable_reason
    assert result.best_path != "D"


def test_special_procedure_blocked_when_recovered_but_not_in_inventory():
    result = run_simulation(
        _input(
            overdue_bucket="M4(91-120天)",
            vehicle_recovered=True,
            vehicle_in_inventory=False,
        )
    )

    assert result.path_d.available is False
    assert "未入库" in result.path_d.unavailable_reason
    assert result.best_path != "D"


def test_special_procedure_available_for_m3_plus_in_inventory():
    result = run_simulation(
        _input(
            overdue_bucket="M3(61-90天)",
            vehicle_recovered=True,
            vehicle_in_inventory=True,
        )
    )

    assert result.path_d.available is True
    assert result.path_d.unavailable_reason == ""


def test_low_liquidity_new_energy_vehicle_reduces_immediate_auction_result():
    mainstream = run_simulation(
        _input(
            car_description="2021 丰田 凯美瑞 2.0G",
            vehicle_type="japanese",
            vehicle_age_years=5,
            energy_type="fuel",
            expected_sale_days=10,
        )
    )
    cold_new_energy = run_simulation(
        _input(
            car_description="2020 威马EX5 纯电 网约 营转非",
            vehicle_type="new_energy",
            vehicle_age_years=6,
            energy_type="bev",
            battery_health_score=68,
            battery_warranty_valid=False,
            ride_hailing_vehicle=True,
            range_km=320,
            expected_sale_days=10,
        )
    )

    assert cold_new_energy.path_c.market_liquidity_level in {"low", "very_low"}
    assert cold_new_energy.path_c.expected_sale_days > mainstream.path_c.expected_sale_days
    assert cold_new_energy.path_c.sale_price < mainstream.path_c.sale_price
    assert "cold_brand_liquidity_risk" in cold_new_energy.path_c.new_energy_risk_tags
