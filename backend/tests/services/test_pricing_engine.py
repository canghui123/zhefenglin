from models.asset import Asset, PricingParameters
from models.valuation import ValuationResult
from services.pricing_engine import build_transfer_report_fallback, calculate_package


def test_inventory_package_uses_vehicle_valuation_as_discount_basis():
    assets = [
        Asset(
            row_number=2,
            car_description="2021 丰田凯美瑞 2.0G",
            loan_principal=120000,
        )
    ]
    valuations = {
        2: ValuationResult(
            model_id="mock_2",
            medium_price=100000,
            good_price=108000,
        )
    }

    result = calculate_package(
        assets,
        PricingParameters(asset_package_type="inventory", vehicle_condition="good"),
        valuations,
    )

    assert result.summary.asset_package_type == "inventory"
    assert result.summary.discount_basis == "车300车辆评估价"
    assert result.summary.total_vehicle_valuation == 108000
    assert result.assets[0].pricing_basis == "车300车辆评估价"
    assert result.assets[0].recommended_transfer_price_mid > 0
    assert result.assets[0].valuation_discount_mid is not None
    assert result.assets[0].collateral_coverage_ratio == 0.9
    assert result.summary.collateral_coverage_ratio == 0.9


def test_non_inventory_package_uses_principal_as_discount_basis():
    assets = [
        Asset(
            row_number=2,
            car_description="2020 本田雅阁 1.5T",
            loan_principal=150000,
            gps_online=False,
        )
    ]
    valuations = {
        2: ValuationResult(
            model_id="mock_2",
            medium_price=90000,
            good_price=98000,
        )
    }

    result = calculate_package(
        assets,
        PricingParameters(asset_package_type="non_inventory", vehicle_condition="good"),
        valuations,
    )

    assert result.summary.asset_package_type == "non_inventory"
    assert result.summary.discount_basis == "债权本金"
    assert result.assets[0].pricing_basis == "债权本金"
    assert result.assets[0].principal_discount_mid == result.assets[0].recommended_discount_mid
    assert any("GPS离线" in flag for flag in result.assets[0].risk_flags)


def test_fallback_report_distinguishes_data_coverage_from_collateral_coverage():
    assets = [
        Asset(
            row_number=2,
            car_description="2021 丰田凯美瑞 2.0G",
            loan_principal=120000,
        )
    ]
    valuations = {
        2: ValuationResult(
            model_id="mock_2",
            medium_price=100000,
            good_price=60000,
        )
    }

    result = calculate_package(
        assets,
        PricingParameters(asset_package_type="inventory", vehicle_condition="good"),
        valuations,
    )

    report = build_transfer_report_fallback(result)

    assert "估值数据覆盖率100.0%" in report
    assert "抵押物价值覆盖" in report
    assert "约为50.0%" in report
    assert "本金覆盖率100" not in report
