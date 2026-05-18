"""资产包出让定价引擎 — 金融公司出让方视角."""

from __future__ import annotations

from typing import Optional

from models.asset import (
    Asset,
    AssetPricingResult,
    PackageCalculationResult,
    PackageSummary,
    PricingParameters,
)
from models.valuation import ValuationResult
from services.package_tradeability import calculate_package_tradeability
from services.valuation_confidence import calculate_valuation_confidence


def _pick_condition_price(valuation: ValuationResult, condition: str) -> Optional[float]:
    """根据车况从估值中选对应价格。"""
    if condition == "excellent":
        return valuation.excellent_price or valuation.good_price or valuation.medium_price
    if condition == "normal":
        return valuation.medium_price or valuation.fair_price or valuation.good_price
    return valuation.good_price or valuation.medium_price or valuation.excellent_price


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def _risk_adjustment(asset: Asset, *, inventory: bool) -> tuple[float, list[str]]:
    """将权属、GPS、保险等处置瑕疵转换为折扣调整。"""
    adjustment = 0.0
    risk_flags: list[str] = []

    if asset.ownership_transferred:
        adjustment -= 0.06
        risk_flags.append("权属瑕疵-建议调低出让价或剔除")

    if asset.insurance_lapsed:
        adjustment -= 0.02
        risk_flags.append("车辆脱保-需在谈判中预留修复成本")

    if asset.gps_online is False:
        adjustment -= 0.02 if inventory else 0.04
        risk_flags.append(
            "GPS离线-非在库资产收车不确定性更高"
            if not inventory
            else "GPS离线-车辆状态核验成本较高"
        )

    return adjustment, risk_flags


def _coverage_adjustment(
    principal: float,
    valuation_price: float,
    *,
    inventory: bool,
) -> tuple[float, Optional[float], Optional[float]]:
    """根据车辆估值对本金覆盖程度调整折扣。"""
    if principal <= 0 or valuation_price <= 0:
        return 0.0, None, None

    coverage = valuation_price / principal
    exposure_gap = principal - valuation_price

    if inventory:
        if coverage >= 0.95:
            return 0.03, coverage, exposure_gap
        if coverage >= 0.75:
            return 0.01, coverage, exposure_gap
        if coverage < 0.45:
            return -0.05, coverage, exposure_gap
        if coverage < 0.6:
            return -0.03, coverage, exposure_gap
        return 0.0, coverage, exposure_gap

    if coverage >= 0.9:
        return 0.08, coverage, exposure_gap
    if coverage >= 0.65:
        return 0.05, coverage, exposure_gap
    if coverage >= 0.45:
        return 0.02, coverage, exposure_gap
    if coverage < 0.25:
        return -0.08, coverage, exposure_gap
    return -0.04, coverage, exposure_gap


def _round_money(value: float) -> float:
    return round(value, 2)


def _discount_range(mid: float, *, inventory: bool) -> tuple[float, float, float]:
    spread = 0.07 if inventory else 0.08
    floor = 0.52 if inventory else 0.12
    ceiling = 0.92 if inventory else 0.68
    low = _clamp(mid - spread, floor, ceiling)
    high = _clamp(mid + spread, floor, ceiling)
    return round(low, 4), round(mid, 4), round(high, 4)


def calculate_single_asset(
    asset: Asset,
    params: PricingParameters,
    valuation: Optional[ValuationResult],
    depreciation_rate: Optional[float] = None,
) -> AssetPricingResult:
    """计算单台资产的出让价格区间。

    在库车资产包：以车300估值为主锚，辅以抵押物价值覆盖率判断议价空间。
    非在库车资产包：以债权本金为主锚，辅以车辆估值判断可回收性。
    """
    inventory = params.asset_package_type == "inventory"
    principal = float(asset.loan_principal or 0)
    valuation_price = 0.0
    if valuation:
        valuation_price = float(_pick_condition_price(valuation, params.vehicle_condition) or 0)

    coverage_adj, coverage, exposure_gap = _coverage_adjustment(
        principal,
        valuation_price,
        inventory=inventory,
    )
    risk_adj, risk_flags = _risk_adjustment(asset, inventory=inventory)

    if inventory:
        basis_amount = valuation_price or principal
        basis_label = "车300车辆评估价"
        base_discount = 0.78
        applied_strategy = "inventory_valuation_discount"
        if valuation_price <= 0:
            risk_flags.append("车辆估值缺失-暂以本金辅助定价")
            base_discount -= 0.06
        if principal <= 0:
            risk_flags.append("本金缺失-无法评估债权覆盖缺口")
    else:
        basis_amount = principal or valuation_price
        basis_label = "债权本金"
        base_discount = 0.36
        applied_strategy = "non_inventory_principal_discount"
        if principal <= 0:
            risk_flags.append("本金缺失-暂以车辆估值辅助定价")
            base_discount = 0.42
        if valuation_price <= 0:
            risk_flags.append("车辆估值缺失-非在库资产缺少抵押物价值校验")
            base_discount -= 0.05

    mid_discount = _clamp(base_discount + coverage_adj + risk_adj, 0.08, 0.95)
    low_discount, mid_discount, high_discount = _discount_range(
        mid_discount,
        inventory=inventory,
    )

    low_price = basis_amount * low_discount
    mid_price = basis_amount * mid_discount
    high_price = basis_amount * high_discount

    principal_discounts = (
        (
            low_price / principal if principal > 0 else None,
            mid_price / principal if principal > 0 else None,
            high_price / principal if principal > 0 else None,
        )
    )
    valuation_discounts = (
        (
            low_price / valuation_price if valuation_price > 0 else None,
            mid_price / valuation_price if valuation_price > 0 else None,
            high_price / valuation_price if valuation_price > 0 else None,
        )
    )

    if coverage is not None:
        if coverage < 0.35:
            risk_flags.append("车辆估值对本金覆盖偏低")
        elif coverage >= 0.9:
            risk_flags.append("抵押物覆盖较强-出让方议价能力较好")

    confidence = calculate_valuation_confidence(
        asset,
        valuation,
        valuation_price=valuation_price or None,
        vehicle_condition=params.vehicle_condition,
        city_available=True,
    )

    if not risk_flags:
        risk_flags.append("基础字段完整-可进入买方询价")

    return AssetPricingResult(
        row_number=asset.row_number,
        car_description=asset.car_description,
        loan_principal=principal or None,
        # 历史兼容字段：现在代表推荐出让价中位数，而不是买入买断成本。
        buyout_price=_round_money(mid_price),
        applied_strategy=applied_strategy,
        che300_valuation=valuation_price or None,
        pricing_basis=basis_label,
        pricing_basis_amount=_round_money(basis_amount),
        recommended_transfer_price_low=_round_money(low_price),
        recommended_transfer_price_mid=_round_money(mid_price),
        recommended_transfer_price_high=_round_money(high_price),
        recommended_discount_low=low_discount,
        recommended_discount_mid=mid_discount,
        recommended_discount_high=high_discount,
        principal_discount_low=(
            round(principal_discounts[0], 4) if principal_discounts[0] is not None else None
        ),
        principal_discount_mid=(
            round(principal_discounts[1], 4) if principal_discounts[1] is not None else None
        ),
        principal_discount_high=(
            round(principal_discounts[2], 4) if principal_discounts[2] is not None else None
        ),
        valuation_discount_low=(
            round(valuation_discounts[0], 4) if valuation_discounts[0] is not None else None
        ),
        valuation_discount_mid=(
            round(valuation_discounts[1], 4) if valuation_discounts[1] is not None else None
        ),
        valuation_discount_high=(
            round(valuation_discounts[2], 4) if valuation_discounts[2] is not None else None
        ),
        collateral_coverage_ratio=round(coverage, 4) if coverage is not None else None,
        exposure_gap=_round_money(exposure_gap) if exposure_gap is not None else None,
        depreciation_rate=depreciation_rate,
        total_cost=0,
        expected_revenue=_round_money(mid_price),
        net_profit=_round_money(mid_price - principal) if principal > 0 else _round_money(mid_price),
        profit_margin=round((mid_price / principal) * 100, 2) if principal > 0 else 0,
        risk_flags=list(dict.fromkeys(risk_flags)),
        valuation_confidence_score=confidence.score,
        valuation_confidence_level=confidence.level,
        valuation_source=confidence.source,
        valuation_warnings=confidence.warnings,
        valuation_anomaly_tags=confidence.anomaly_tags,
    )


def _sum_optional(values: list[Optional[float]]) -> float:
    return sum(float(v or 0) for v in values)


def _weighted_discount(
    numerator: float,
    denominator: float,
) -> Optional[float]:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def calculate_package(
    assets: list[Asset],
    params: PricingParameters,
    valuations: dict[int, ValuationResult],
    depreciation_rates: Optional[dict[int, float]] = None,
) -> PackageCalculationResult:
    """计算整个资产包的出让定价建议。"""
    depreciation_rates = depreciation_rates or {}
    results: list[AssetPricingResult] = []
    for asset in assets:
        val = valuations.get(asset.row_number)
        dep = depreciation_rates.get(asset.row_number)
        results.append(calculate_single_asset(asset, params, val, dep))

    total_principal = _sum_optional([r.loan_principal for r in results])
    total_valuation = _sum_optional([r.che300_valuation for r in results])
    low_total = sum(r.recommended_transfer_price_low for r in results)
    mid_total = sum(r.recommended_transfer_price_mid for r in results)
    high_total = sum(r.recommended_transfer_price_high for r in results)
    valued_count = sum(1 for r in results if r.che300_valuation and r.che300_valuation > 0)

    inventory = params.asset_package_type == "inventory"
    discount_denominator = total_valuation if inventory else total_principal
    discount_basis = "车300车辆评估价" if inventory else "债权本金"

    principal_low = _weighted_discount(low_total, total_principal)
    principal_mid = _weighted_discount(mid_total, total_principal)
    principal_high = _weighted_discount(high_total, total_principal)
    valuation_low = _weighted_discount(low_total, total_valuation)
    valuation_mid = _weighted_discount(mid_total, total_valuation)
    valuation_high = _weighted_discount(high_total, total_valuation)

    risk_alerts: list[str] = []
    missing_principal = [r for r in results if not r.loan_principal]
    missing_valuation = [r for r in results if not r.che300_valuation]
    low_coverage = [
        r
        for r in results
        if r.collateral_coverage_ratio is not None and r.collateral_coverage_ratio < 0.35
    ]
    title_risks = [
        r
        for r in results
        if any("权属瑕疵" in flag for flag in r.risk_flags)
    ]

    if missing_principal:
        risk_alerts.append(f"有{len(missing_principal)}台缺少本金，出让折扣口径需人工复核")
    if missing_valuation:
        risk_alerts.append(f"有{len(missing_valuation)}台未取得有效车辆估值，建议补充VIN/上牌/里程")
    if low_coverage:
        risk_alerts.append(f"有{len(low_coverage)}台车辆估值对本金覆盖低于35%，买方可能压价")
    if title_risks:
        risk_alerts.append(f"有{len(title_risks)}台存在权属瑕疵，建议剔除或单独披露")

    if inventory:
        methodology = (
            "在库车资产包以车300车辆评估价为主锚，结合抵押物价值覆盖率、权属/GPS/保险等瑕疵给出"
            "出让折扣区间；该口径适合已控制车辆、可验证车况、买方可快速处置的资产。"
        )
    else:
        methodology = (
            "非在库车资产包以债权本金为主锚，车辆评估价用于校验抵押物覆盖和收车可实现性；"
            "该口径更重视回收不确定性、收车周期和买方资金占用。"
        )

    strategy_breakdown: dict[str, int] = {}
    for row in results:
        strategy_breakdown[row.applied_strategy] = (
            strategy_breakdown.get(row.applied_strategy, 0) + 1
        )

    summary = PackageSummary(
        total_assets=len(results),
        # 历史兼容字段：前端旧版本可能仍读取 total_buyout_cost。
        total_buyout_cost=_round_money(mid_total),
        total_expected_revenue=_round_money(mid_total),
        total_net_profit=_round_money(mid_total - total_principal),
        overall_roi=round((mid_total / total_principal) * 100, 2) if total_principal > 0 else 0,
        recommended_max_discount=_weighted_discount(mid_total, discount_denominator) or 0,
        asset_package_type=params.asset_package_type,
        discount_basis=discount_basis,
        total_principal=_round_money(total_principal),
        total_vehicle_valuation=_round_money(total_valuation),
        valuation_coverage_rate=round(valued_count / len(results) * 100, 2) if results else 0,
        recommended_transfer_price_low=_round_money(low_total),
        recommended_transfer_price_mid=_round_money(mid_total),
        recommended_transfer_price_high=_round_money(high_total),
        recommended_discount_low=_weighted_discount(low_total, discount_denominator) or 0,
        recommended_discount_mid=_weighted_discount(mid_total, discount_denominator) or 0,
        recommended_discount_high=_weighted_discount(high_total, discount_denominator) or 0,
        principal_recovery_rate_low=principal_low,
        principal_recovery_rate_mid=principal_mid,
        principal_recovery_rate_high=principal_high,
        valuation_realization_rate_low=valuation_low,
        valuation_realization_rate_mid=valuation_mid,
        valuation_realization_rate_high=valuation_high,
        collateral_coverage_ratio=_weighted_discount(total_valuation, total_principal),
        pricing_methodology=methodology,
        high_risk_count=len(low_coverage) + len(title_risks),
        risk_alerts=risk_alerts,
        requested_strategy="seller_transfer_analysis",
        discount_rate_used=None,
        strategy_breakdown=strategy_breakdown,
    )
    tradeability = calculate_package_tradeability(summary, results)
    summary.tradeability_score = tradeability.score
    summary.tradeability_level = tradeability.level
    summary.tradeability_summary = tradeability.summary
    summary.tradeability_recommendations = tradeability.recommendations
    summary.tradeability_breakdown = tradeability.breakdown

    return PackageCalculationResult(
        package_id=0,
        summary=summary,
        assets=results,
    )


def build_transfer_report_fallback(result: PackageCalculationResult) -> str:
    """LLM不可用时返回可演示的模板化出让分析报告。"""
    summary = result.summary
    package_label = "在库车资产包" if summary.asset_package_type == "inventory" else "非在库车资产包"
    discount_mid = summary.recommended_discount_mid * 100
    principal_mid = (
        summary.principal_recovery_rate_mid * 100
        if summary.principal_recovery_rate_mid is not None
        else None
    )
    valuation_mid = (
        summary.valuation_realization_rate_mid * 100
        if summary.valuation_realization_rate_mid is not None
        else None
    )

    lines = [
        f"一、资产包定位：本次资产包被识别为{package_label}，共{summary.total_assets}台车。",
        f"二、核心规模：债权本金合计约{summary.total_principal:,.0f}元，车300评估价合计约{summary.total_vehicle_valuation:,.0f}元，估值数据覆盖率{summary.valuation_coverage_rate:.1f}%。",
        f"三、推荐出让价：建议挂牌/谈判区间为{summary.recommended_transfer_price_low:,.0f}元至{summary.recommended_transfer_price_high:,.0f}元，中位建议{summary.recommended_transfer_price_mid:,.0f}元。",
        f"四、折扣口径：本次以{summary.discount_basis}为主锚，中位折扣约{discount_mid:.1f}%。",
        f"五、交易适配度：{summary.tradeability_level}级/{summary.tradeability_score}分，{summary.tradeability_summary}",
    ]
    if summary.collateral_coverage_ratio is not None:
        lines.append(
            f"六、抵押物价值覆盖：车300估值合计/债权本金合计约为{summary.collateral_coverage_ratio * 100:.1f}%。"
        )
    if principal_mid is not None:
        lines.append(f"七、本金回收：中位出让价相当于本金回收率约{principal_mid:.1f}%。")
    if valuation_mid is not None:
        lines.append(f"八、车辆价值实现：中位出让价相当于车辆评估价实现率约{valuation_mid:.1f}%。")
    if summary.risk_alerts:
        lines.append("九、主要风险：" + "；".join(summary.risk_alerts) + "。")
    lines.append(
        "十、谈判建议：金融公司作为出让方，应以中位价作为内部底线参考，以上沿价格作为首轮报价，"
        "对缺少VIN、估值缺失、权属瑕疵或非在库资产的不确定性单独披露，避免被买方整体压价。"
    )
    return "\n".join(lines)
