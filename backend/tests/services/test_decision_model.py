from db.session import get_db_session
from services.decision_model import (
    adjusted_duration_days,
    adjusted_towing_cost,
    dynamic_success_probability,
    estimate_depreciation_rate,
    resolve_brand_profile,
    resolve_region_coefficient,
)
from scripts.seed_decision_model_defaults import seed_decision_model_defaults


def test_dynamic_success_probability_declines_with_risk_inputs():
    profile = resolve_brand_profile(vehicle_type="japanese")
    region = resolve_region_coefficient()

    low_risk = dynamic_success_probability(
        base_probability=0.8,
        vehicle_age_years=2,
        overdue_amount=50_000,
        vehicle_value=150_000,
        profile=profile,
        region=region,
        path_type="retail_auction",
    )
    high_risk = dynamic_success_probability(
        base_probability=0.8,
        vehicle_age_years=9,
        overdue_amount=180_000,
        vehicle_value=150_000,
        profile=profile,
        region=region,
        path_type="retail_auction",
    )

    assert high_risk < low_risk


def test_special_procedure_probability_zero_without_inventory_control():
    profile = resolve_brand_profile(vehicle_type="domestic")
    region = resolve_region_coefficient()

    probability = dynamic_success_probability(
        base_probability=0.7,
        vehicle_age_years=3,
        overdue_amount=80_000,
        vehicle_value=120_000,
        profile=profile,
        region=region,
        path_type="special_procedure",
        vehicle_recovered=True,
        vehicle_in_inventory=False,
    )

    assert probability == 0


def test_new_energy_depreciates_faster_than_same_age_fuel_vehicle():
    domestic = resolve_brand_profile(vehicle_type="domestic")
    new_energy = resolve_brand_profile(vehicle_type="new_energy")

    domestic_dep = estimate_depreciation_rate(
        days=90,
        vehicle_age_years=3,
        profile=domestic,
    )
    new_energy_dep = estimate_depreciation_rate(
        days=90,
        vehicle_age_years=3,
        profile=new_energy,
    )

    assert new_energy_dep > domestic_dep


def test_region_coefficient_adjusts_towing_and_duration():
    region = resolve_region_coefficient(province="四川省")

    assert adjusted_towing_cost(1_000, region) > 1_000
    assert adjusted_duration_days(90, region=region, path_type="litigation") > 90


def test_decision_model_seed_is_idempotent():
    gen = get_db_session()
    session = next(gen)
    try:
        first = seed_decision_model_defaults(session)
        second = seed_decision_model_defaults(session)
    finally:
        try:
            next(gen)
        except StopIteration:
            pass

    assert first["brand_profiles"] >= 4
    assert second == first
