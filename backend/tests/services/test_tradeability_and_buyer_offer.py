from models.asset import AssetPricingResult, PackageCalculationResult, PackageSummary
from services.buyer_offer_analysis import analyze_buyer_offer
from services.package_tradeability import calculate_package_tradeability


def _asset(**overrides) -> AssetPricingResult:
    data = {
        "row_number": 2,
        "car_description": "2022 丰田 凯美瑞 2.0G",
        "loan_principal": 120000,
        "buyout_price": 0,
        "applied_strategy": "inventory_valuation_discount",
        "che300_valuation": 100000,
        "pricing_basis": "车300车辆评估价",
        "pricing_basis_amount": 100000,
        "recommended_transfer_price_low": 71000,
        "recommended_transfer_price_mid": 78000,
        "recommended_transfer_price_high": 85000,
        "recommended_discount_low": 0.71,
        "recommended_discount_mid": 0.78,
        "recommended_discount_high": 0.85,
        "principal_discount_low": 0.59,
        "principal_discount_mid": 0.65,
        "principal_discount_high": 0.71,
        "valuation_discount_low": 0.71,
        "valuation_discount_mid": 0.78,
        "valuation_discount_high": 0.85,
        "collateral_coverage_ratio": 0.83,
        "exposure_gap": 20000,
        "risk_flags": ["基础字段完整-可进入买方询价"],
        "valuation_confidence_score": 86,
        "valuation_confidence_level": "high",
        "valuation_source": "che300_vin",
    }
    data.update(overrides)
    return AssetPricingResult(**data)


def _summary(**overrides) -> PackageSummary:
    data = {
        "total_assets": 2,
        "asset_package_type": "inventory",
        "discount_basis": "车300车辆评估价",
        "total_principal": 240000,
        "total_vehicle_valuation": 200000,
        "valuation_coverage_rate": 100,
        "recommended_transfer_price_low": 142000,
        "recommended_transfer_price_mid": 156000,
        "recommended_transfer_price_high": 170000,
        "recommended_discount_low": 0.71,
        "recommended_discount_mid": 0.78,
        "recommended_discount_high": 0.85,
        "collateral_coverage_ratio": 0.83,
    }
    data.update(overrides)
    return PackageSummary(**data)


def test_tradeability_high_quality_package_is_a_or_b():
    summary = _summary()
    assets = [_asset(row_number=2), _asset(row_number=3)]

    result = calculate_package_tradeability(summary, assets)

    assert result.level in {"A", "B"}
    assert result.score >= 70
    assert "估值覆盖完整度" in result.breakdown


def test_tradeability_downgrades_missing_values_and_title_risks():
    summary = _summary(collateral_coverage_ratio=0.2, total_vehicle_valuation=0)
    assets = [
        _asset(
            che300_valuation=None,
            loan_principal=None,
            risk_flags=["权属瑕疵：疑似过户", "抵押物覆盖偏低"],
            valuation_confidence_score=20,
            valuation_confidence_level="very_low",
        )
    ]

    result = calculate_package_tradeability(summary, assets)

    assert result.level in {"D", "E"}
    assert any("缺失估值" in item for item in result.recommendations)
    assert any("权属异常" in item for item in result.recommendations)


def test_buyer_offer_uses_vehicle_valuation_for_inventory_discount():
    package = PackageCalculationResult(
        package_id=11,
        summary=_summary(),
        assets=[_asset(row_number=2), _asset(row_number=3)],
    )

    analysis = analyze_buyer_offer(package, buyer_offer_price=150000)

    assert analysis.buyer_offer_discount == 0.75
    assert analysis.buyer_offer_gap == 6000
    assert 0 < analysis.buyer_offer_gap_rate < 0.1
    assert "可接受谈判区间" in analysis.buyer_offer_assessment


def test_buyer_offer_uses_principal_for_non_inventory_discount_and_flags_low_offer():
    package = PackageCalculationResult(
        package_id=11,
        summary=_summary(
            asset_package_type="non_inventory",
            discount_basis="债权本金",
            total_principal=300000,
            total_vehicle_valuation=200000,
            recommended_transfer_price_mid=210000,
        ),
        assets=[_asset(row_number=2), _asset(row_number=3)],
    )

    analysis = analyze_buyer_offer(package, buyer_offer_price=120000)

    assert analysis.buyer_offer_discount == 0.4
    assert analysis.buyer_offer_gap_rate and analysis.buyer_offer_gap_rate > 0.25
    assert "疑似压价" in analysis.buyer_offer_assessment
