"""Buyer offer reverse analysis for asset package transfer negotiation."""

from __future__ import annotations

from models.asset import BuyerOfferAnalysis, PackageCalculationResult


def analyze_buyer_offer(
    result: PackageCalculationResult,
    *,
    buyer_offer_price: float,
    buyer_offer_note: str | None = None,
) -> BuyerOfferAnalysis:
    if buyer_offer_price <= 0:
        raise ValueError("buyer_offer_price 必须为正数")

    summary = result.summary
    recommended_mid = float(summary.recommended_transfer_price_mid or 0)
    denominator = (
        float(summary.total_vehicle_valuation or 0)
        if summary.asset_package_type == "inventory"
        else float(summary.total_principal or 0)
    )

    buyer_offer_gap = recommended_mid - buyer_offer_price
    buyer_offer_gap_rate = (
        buyer_offer_gap / recommended_mid if recommended_mid > 0 else None
    )
    buyer_offer_discount = (
        buyer_offer_price / denominator if denominator > 0 else None
    )

    suggestions: list[str] = []
    if buyer_offer_gap_rate is None:
        assessment = "系统推荐中位价缺失，暂无法判断买方报价合理性"
        suggestions.append("请先重新生成资产包出让分析后再录入买方报价")
    elif buyer_offer_gap_rate <= 0:
        assessment = "买方报价高于或等于系统中位建议，可关注付款条件和履约风险"
        suggestions.append("重点核查付款周期、保证金、违约责任和交割条件")
    elif buyer_offer_gap_rate <= 0.10:
        assessment = "买方报价处于可接受谈判区间"
        suggestions.append("可围绕交割速度、瑕疵披露和批量成交条件进行谈判")
    elif buyer_offer_gap_rate <= 0.25:
        assessment = "买方报价明显低于建议价，需买方说明风险折价依据"
        suggestions.append("要求买方逐项说明GPS离线、脱保、权属异常或估值缺失的折价依据")
        suggestions.append("建议以系统中位价作为内部谈判底线，必要时拆分争议资产")
    else:
        assessment = "买方报价疑似压价，建议拆解争议资产并组织二轮询价"
        suggestions.append("建议剔除高风险资产后重新询价，避免优质资产被整体压价")
        suggestions.append("可邀请第二轮买方报价或改为小包竞价")

    if summary.risk_alerts:
        suggestions.append("谈判时需同步披露并量化系统风险预警，避免买方扩大化压价")

    return BuyerOfferAnalysis(
        buyer_offer_price=round(buyer_offer_price, 2),
        buyer_offer_note=buyer_offer_note,
        buyer_offer_discount=round(buyer_offer_discount, 4)
        if buyer_offer_discount is not None
        else None,
        buyer_offer_gap=round(buyer_offer_gap, 2),
        buyer_offer_gap_rate=round(buyer_offer_gap_rate, 4)
        if buyer_offer_gap_rate is not None
        else None,
        buyer_offer_assessment=assessment,
        negotiation_suggestions=list(dict.fromkeys(suggestions)),
    )
