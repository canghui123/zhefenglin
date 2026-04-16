"""资产包买断定价引擎 — 多维成本测算 + 风险标签"""

from typing import Optional

from models.asset import (
    Asset, PricingParameters, AssetPricingResult, PackageSummary, PackageCalculationResult,
)
from models.valuation import ValuationResult


def _pick_condition_price(valuation: ValuationResult, condition: str) -> Optional[float]:
    """根据车况从估值中选对应价格"""
    if condition == "excellent":
        return valuation.excellent_price or valuation.good_price or valuation.medium_price
    if condition == "normal":
        return valuation.medium_price or valuation.fair_price or valuation.good_price
    # 默认 good（良好）
    return valuation.good_price or valuation.medium_price or valuation.excellent_price


def _compute_buyout(asset: Asset, params: PricingParameters) -> float:
    """根据策略计算单车买断价"""
    strategy = params.buyout_strategy
    if strategy == "discount":
        if asset.loan_principal and params.discount_rate:
            return round(asset.loan_principal * params.discount_rate, 2)
        return 0
    if strategy == "ai_suggest":
        # ai_suggest 模式下 buyout_price 由 AI endpoint 预先写入 asset.buyout_price
        return asset.buyout_price or 0
    # direct 模式：直接用 Excel 解析出的 buyout_price
    return asset.buyout_price or 0


def calculate_single_asset(
    asset: Asset,
    params: PricingParameters,
    valuation: Optional[ValuationResult],
    depreciation_rate: Optional[float],
) -> AssetPricingResult:
    """计算单台车的成本、收入、利润和风险"""
    buyout = _compute_buyout(asset, params)
    risk_flags = []

    # --- 成本计算 ---
    towing = params.towing_cost
    parking = params.daily_parking * params.disposal_period
    capital = buyout * (params.capital_rate / 100) * (params.disposal_period / 365)
    total_cost = buyout + towing + parking + capital

    # --- 收入预估 ---
    che300_val = None
    expected_revenue = 0

    if valuation:
        che300_val = _pick_condition_price(valuation, params.vehicle_condition)

    if che300_val:
        dep_rate = depreciation_rate if depreciation_rate is not None else 0.02
        expected_revenue = che300_val * (1 - dep_rate)
    elif buyout > 0:
        # 无估值时，保守估计收入=买断价*1.1
        expected_revenue = buyout * 1.1

    net_profit = expected_revenue - total_cost
    profit_margin = (net_profit / total_cost * 100) if total_cost > 0 else 0

    # --- 风险标签 ---
    if asset.ownership_transferred:
        risk_flags.append("已过户-权属瑕疵")

    if asset.insurance_lapsed:
        risk_flags.append("已脱保-需补缴")

    if asset.gps_online is False:
        risk_flags.append("GPS离线-拖回困难")
        # 调整拖车费（离线更贵/成功率更低）
        towing = params.towing_cost * 1.5

    if che300_val and buyout > 0:
        buyout_ratio = buyout / che300_val
        if buyout_ratio > 0.7:
            risk_flags.append(f"买断价偏高(占估值{buyout_ratio:.0%})")

    if profit_margin < 5:
        risk_flags.append("利润率过低(<5%)")

    if profit_margin < 0:
        risk_flags.append("预计亏损")

    # 重新算（GPS离线调整后）
    total_cost = buyout + towing + parking + capital
    net_profit = expected_revenue - total_cost
    profit_margin = (net_profit / total_cost * 100) if total_cost > 0 else 0

    return AssetPricingResult(
        row_number=asset.row_number,
        car_description=asset.car_description,
        buyout_price=buyout,
        che300_valuation=che300_val,
        depreciation_rate=depreciation_rate,
        towing_cost=towing,
        parking_cost=parking,
        capital_cost=round(capital, 2),
        total_cost=round(total_cost, 2),
        expected_revenue=round(expected_revenue, 2),
        net_profit=round(net_profit, 2),
        profit_margin=round(profit_margin, 2),
        risk_flags=risk_flags,
    )


def calculate_package(
    assets: list[Asset],
    params: PricingParameters,
    valuations: dict[int, ValuationResult],
    depreciation_rates: dict[int, float],
) -> PackageCalculationResult:
    """计算整个资产包"""
    results = []
    for asset in assets:
        val = valuations.get(asset.row_number)
        dep = depreciation_rates.get(asset.row_number)
        result = calculate_single_asset(asset, params, val, dep)
        results.append(result)

    # 汇总
    total_buyout = sum(r.buyout_price for r in results)
    total_revenue = sum(r.expected_revenue for r in results)
    total_profit = sum(r.net_profit for r in results)
    total_cost = sum(r.total_cost for r in results)
    overall_roi = (total_profit / total_cost * 100) if total_cost > 0 else 0

    high_risk = [r for r in results if len(r.risk_flags) >= 2]
    loss_items = [r for r in results if r.net_profit < 0]
    transferred = [r for r in results if "已过户-权属瑕疵" in r.risk_flags]

    # 建议最高买断折扣
    if total_revenue > 0:
        # 要保证至少10%利润率
        max_affordable_buyout = total_revenue / 1.10 - sum(
            r.towing_cost + r.parking_cost + r.capital_cost for r in results
        )
        recommended_discount = (max_affordable_buyout / total_revenue) if total_revenue > 0 else 0
    else:
        recommended_discount = 0

    risk_alerts = []
    if transferred:
        risk_alerts.append(f"有{len(transferred)}台车已被过户，权属存在瑕疵，建议剔除")
    if loss_items:
        risk_alerts.append(f"有{len(loss_items)}台车预计亏损，需重点关注")
    gps_offline = [r for r in results if "GPS离线-拖回困难" in r.risk_flags]
    if gps_offline:
        risk_alerts.append(f"有{len(gps_offline)}台车GPS离线，拖回成功率低")

    summary = PackageSummary(
        total_assets=len(results),
        total_buyout_cost=round(total_buyout, 2),
        total_expected_revenue=round(total_revenue, 2),
        total_net_profit=round(total_profit, 2),
        overall_roi=round(overall_roi, 2),
        recommended_max_discount=round(recommended_discount, 4),
        high_risk_count=len(high_risk),
        risk_alerts=risk_alerts,
    )

    return PackageCalculationResult(
        package_id=0,
        summary=summary,
        assets=results,
    )
