from models.external_data import FindCarSignalRequest, JudicialRiskRequest
from services.external_data_gateway import (
    assess_judicial_risk,
    compute_find_car_score,
    list_provider_capabilities,
)


def test_provider_capabilities_are_reserved_for_expected_data_sources():
    providers = list_provider_capabilities()
    codes = {provider.provider_code for provider in providers}

    assert {"gps_trace", "etc_trace", "traffic_violation", "judicial_risk"} <= codes


def test_find_car_score_increases_with_fresh_external_signals():
    weak = compute_find_car_score(FindCarSignalRequest())
    strong = compute_find_car_score(
        FindCarSignalRequest(
            city="南京市",
            gps_recent_days=1,
            etc_recent_days=5,
            violation_recent_days=7,
        )
    )

    assert strong.score > weak.score
    assert strong.level == "high"
    assert strong.signals


def test_judicial_risk_blocks_collection_for_dishonest_enforced_debtor():
    result = assess_judicial_risk(
        JudicialRiskRequest(
            debtor_name="张三",
            dishonest_enforced=True,
            restricted_consumption=True,
            litigation_count=3,
        )
    )

    assert result.collection_blocked is True
    assert result.risk_level == "high"
    assert any("失信" in tag for tag in result.risk_tags)
