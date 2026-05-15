from datetime import date

from models.asset import Asset
from models.valuation import ValuationResult
from services.valuation_confidence import calculate_valuation_confidence


def test_real_vin_complete_data_gets_high_confidence():
    asset = Asset(
        row_number=2,
        car_description="2022 丰田 凯美瑞 2.0G 豪华版",
        vin="LVGBM51K9NG123456",
        first_registration=date(2022, 6, 1),
        mileage=3.2,
        loan_principal=120000,
    )
    valuation = ValuationResult(
        model_id="che300_123",
        medium_price=100000,
        good_price=108000,
        is_mock=False,
        source="che300_vin",
    )

    result = calculate_valuation_confidence(
        asset,
        valuation,
        valuation_price=108000,
        vehicle_condition="good",
    )

    assert result.score >= 80
    assert result.level == "high"
    assert result.source == "che300_vin"
    assert "使用mock估值" not in " ".join(result.warnings)


def test_mock_valuation_is_capped_at_40():
    asset = Asset(
        row_number=2,
        car_description="2022 丰田 凯美瑞 2.0G 豪华版",
        vin="LVGBM51K9NG123456",
        first_registration=date(2022, 6, 1),
        mileage=3.2,
        loan_principal=120000,
    )
    valuation = ValuationResult(
        model_id="mock_2",
        medium_price=100000,
        good_price=108000,
        is_mock=True,
        source="mock",
    )

    result = calculate_valuation_confidence(
        asset,
        valuation,
        valuation_price=108000,
        vehicle_condition="good",
    )

    assert result.score <= 40
    assert result.level == "mock"
    assert any("mock估值" in warning for warning in result.warnings)


def test_missing_fields_and_abnormal_valuation_ratio_generate_warnings_and_tags():
    asset = Asset(
        row_number=2,
        car_description="车辆",
        loan_principal=50000,
    )
    valuation = ValuationResult(
        model_id="che300_123",
        medium_price=100000,
        good_price=100000,
        is_mock=False,
        source="che300_model",
    )

    result = calculate_valuation_confidence(
        asset,
        valuation,
        valuation_price=100000,
        vehicle_condition="good",
    )

    assert result.score < 60
    assert "VIN缺失或格式不完整" in result.warnings
    assert "上牌日期缺失" in result.warnings
    assert "里程缺失或异常" in result.warnings
    assert "model_description_fuzzy" in result.anomaly_tags
    assert "valuation_much_higher_than_principal" in result.anomaly_tags
