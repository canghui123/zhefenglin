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
    assert result.path_d.success_probability == 0
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
    assert result.path_d.success_probability == 0
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
    assert result.path_d.success_probability == 0
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
    assert result.path_d.success_probability > 0


def test_future_marginal_net_benefit_excludes_sunk_costs():
    without_sunk = run_simulation(_input())
    with_sunk = run_simulation(
        _input(sunk_collection_cost=8000, sunk_legal_cost=5000)
    )

    assert with_sunk.path_c.future_marginal_net_benefit == without_sunk.path_c.future_marginal_net_benefit
    assert with_sunk.path_c.sunk_cost_excluded == 13000
    assert "未来边际净收益" in with_sunk.recommendation


def test_dishonest_enforced_debtor_blocks_waiting_path():
    result = run_simulation(
        _input(
            debtor_dishonest_enforced=True,
            vehicle_recovered=True,
            vehicle_in_inventory=True,
        )
    )

    assert result.path_a.available is False
    assert result.path_a.success_probability == 0
    assert all(tp.success_probability == 0 for tp in result.path_a.timepoints)
    assert result.best_path != "A"
    assert "失信被执行人" in result.path_a.unavailable_reason
