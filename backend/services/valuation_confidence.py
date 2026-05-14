"""Valuation confidence and anomaly scoring for asset package pricing."""

from __future__ import annotations

from datetime import date
from typing import Optional

from models.asset import Asset, ValuationConfidenceResult
from models.valuation import ValuationResult


def _is_valid_vin(vin: Optional[str]) -> bool:
    return bool(vin and len(vin.strip()) == 17 and vin.strip().isalnum())


def _is_fuzzy_model(description: str) -> bool:
    text = (description or "").strip()
    if len(text) < 6:
        return True
    fuzzy_words = ("未知", "不详", "车辆", "汽车", "轿车", "SUV", "车型")
    return text in fuzzy_words


def _level(score: int, *, is_mock: bool) -> str:
    if is_mock:
        return "mock"
    if score >= 80:
        return "high"
    if score >= 60:
        return "medium"
    if score >= 40:
        return "low"
    return "very_low"


def calculate_valuation_confidence(
    asset: Asset,
    valuation: Optional[ValuationResult],
    *,
    valuation_price: Optional[float],
    vehicle_condition: str,
    city_available: bool = True,
) -> ValuationConfidenceResult:
    """Return a 0-100 confidence score for using a valuation in a formal report."""
    score = 0
    warnings: list[str] = []
    anomaly_tags: list[str] = []

    vin_valid = _is_valid_vin(asset.vin)
    if vin_valid:
        score += 25
    else:
        warnings.append("VIN缺失或格式不完整")

    if asset.first_registration is not None:
        score += 15
    else:
        warnings.append("上牌日期缺失")

    if asset.mileage is not None and 0 < asset.mileage <= 80:
        score += 15
    else:
        warnings.append("里程缺失或异常")

    if vehicle_condition in {"excellent", "good", "normal"}:
        score += 15

    if city_available:
        score += 10
    else:
        warnings.append("城市/区域价格参数缺失")

    is_mock = bool(valuation and valuation.is_mock)
    source = valuation.source if valuation else "missing"
    if valuation and valuation.from_cache:
        score += 5
    if valuation and not valuation.is_mock and valuation_price and valuation_price > 0:
        score += 15
    elif not valuation_price:
        warnings.append("未取得有效车辆估值")

    if is_mock:
        score = min(score, 40)
        warnings.append("使用mock估值，仅适合演示或临时测算")

    if not vin_valid and _is_fuzzy_model(asset.car_description):
        score -= 20
        anomaly_tags.append("model_description_fuzzy")

    if asset.mileage is None:
        score -= 10
    if asset.first_registration is None:
        score -= 10

    if valuation_price and asset.loan_principal and asset.loan_principal > 0:
        ratio = valuation_price / asset.loan_principal
        if ratio > 1.5:
            score -= 10
            anomaly_tags.append("valuation_much_higher_than_principal")
            warnings.append("估值显著高于债权，请复核本金或车型")
        if ratio < 0.25:
            score -= 10
            anomaly_tags.append("collateral_coverage_severely_low")
            warnings.append("抵押物覆盖严重不足")

    if asset.first_registration is not None and asset.mileage is None:
        age_years = (date.today() - asset.first_registration).days / 365.25
        if age_years > 5:
            anomaly_tags.append("old_vehicle_missing_mileage")
            warnings.append("车龄超过5年但里程缺失，估值可信度下降")

    if any(keyword in asset.car_description for keyword in ("新能源", "纯电", "插混", "PHEV", "EV", "特斯拉", "比亚迪")):
        if asset.first_registration is not None:
            age_years = (date.today() - asset.first_registration).days / 365.25
            if age_years > 3 and valuation_price and asset.loan_principal and valuation_price / asset.loan_principal > 0.9:
                score -= 10
                anomaly_tags.append("new_energy_high_residual_value_risk")
                warnings.append("新能源车龄超过3年且估值偏高，需关注残值波动")
        warnings.append("新能源车辆建议补充电池健康/质保信息")

    score = max(0, min(int(round(score)), 100))
    deduped_warnings = list(dict.fromkeys(warnings))
    deduped_tags = list(dict.fromkeys(anomaly_tags))
    return ValuationConfidenceResult(
        score=score,
        level=_level(score, is_mock=is_mock),
        source=source,
        warnings=deduped_warnings,
        anomaly_tags=deduped_tags,
    )
