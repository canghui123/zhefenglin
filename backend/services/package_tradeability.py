"""Package-level tradeability scoring for seller-side asset transfers."""

from __future__ import annotations

from typing import Optional

from models.asset import Asset, AssetPricingResult, PackageSummary, TradeabilityResult
from services.overdue_segmentation import storage_timeliness_score


def _ratio(ok_count: int, total: int) -> float:
    if total <= 0:
        return 0
    return ok_count / total


def _level(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "E"


def _timeliness_from_source_assets(
    source_assets: list[Asset],
    *,
    max_score: float = 10.0,
) -> float:
    """B1: 真正的"处置时效性" = 在库状态 + 在库天数加权平均。

    每台车按 `storage_timeliness_score()` 算 0..max_score,然后取均值。
    """
    if not source_assets:
        return 0.0
    scores = [
        storage_timeliness_score(
            in_storage=a.in_storage,
            storage_days=a.storage_days,
            max_score=max_score,
        )
        for a in source_assets
    ]
    return sum(scores) / len(scores)


def calculate_package_tradeability(
    summary: PackageSummary,
    assets: list[AssetPricingResult],
    *,
    source_assets: Optional[list[Asset]] = None,
) -> TradeabilityResult:
    """计算资产包交易适配度。

    Args:
        summary:  已经填完业务字段的 PackageSummary(B1 含逾期/在库/缺 VIN 聚合)
        assets:   定价后的 AssetPricingResult 列表(用来算各类风险占比)
        source_assets: B1 新增 - source pydantic Asset 列表,带 in_storage /
                      storage_days / overdue_days 等业务字段,用来算"处置时效性"。
                      为 None 时退回旧的"估值可信度"代理逻辑(向后兼容)。
    """
    total = max(len(assets), 1)
    valued = sum(1 for row in assets if row.che300_valuation and row.che300_valuation > 0)
    with_principal = sum(1 for row in assets if row.loan_principal and row.loan_principal > 0)
    no_gps_risk = sum(1 for row in assets if not any("GPS离线" in flag for flag in row.risk_flags))
    no_title_risk = sum(1 for row in assets if not any("权属瑕疵" in flag for flag in row.risk_flags))
    no_low_coverage = sum(1 for row in assets if not any("覆盖偏低" in flag for flag in row.risk_flags))
    no_low_liquidity = sum(
        1 for row in assets if row.market_liquidity_level not in {"low", "very_low"}
    )
    no_low_confidence = sum(
        1
        for row in assets
        if row.valuation_confidence_level in {"high", "medium"}
    )
    avg_confidence = (
        sum(row.valuation_confidence_score for row in assets) / total if assets else 0
    )

    valuation_component = 20 * _ratio(valued, total) * max(avg_confidence, 40) / 100
    principal_component = 15 * _ratio(with_principal, total)
    coverage_ratio = summary.collateral_coverage_ratio or 0
    coverage_component = 20 * min(max(coverage_ratio / 0.8, 0), 1.1)
    coverage_component = min(coverage_component, 20)
    control_component = 15 * _ratio(no_gps_risk, total)
    title_component = 10 * _ratio(no_title_risk, total)
    # B1: 处置时效性优先用 source assets 算(在库 + 在库天数);
    # 没有 source 时退回旧的估值可信度代理(向后兼容)
    if source_assets:
        timeliness_component = _timeliness_from_source_assets(source_assets, max_score=10.0)
    else:
        timeliness_component = 10 * _ratio(no_low_confidence, total)
    buyer_acceptance_component = 10 * min(
        _ratio(no_low_coverage, total),
        _ratio(no_low_liquidity, total),
    )

    breakdown = {
        "估值覆盖完整度": round(valuation_component, 2),
        "本金数据完整度": round(principal_component, 2),
        "抵押物覆盖率": round(coverage_component, 2),
        "车辆控制状态": round(control_component, 2),
        "权属清晰度": round(title_component, 2),
        "处置时效性": round(timeliness_component, 2),
        "买方接受度": round(buyer_acceptance_component, 2),
    }
    score = int(round(sum(breakdown.values())))
    score = max(0, min(score, 100))
    level = _level(score)

    recommendations: list[str] = []
    if valued < total:
        recommendations.append(f"建议补齐{total - valued}台缺失估值资产的VIN/上牌/里程")
    if with_principal < total:
        recommendations.append(f"建议补齐{total - with_principal}台缺失本金资产")
    if no_title_risk < total:
        recommendations.append(f"建议剔除或单独披露{total - no_title_risk}台权属异常资产")
    if coverage_ratio and coverage_ratio < 0.45:
        recommendations.append("整体抵押物覆盖偏低，建议拆包或先转清收/诉讼路径")
    if avg_confidence < 60:
        recommendations.append("估值可信度偏低，正式出让前建议补资料或调用高级车况定价")
    if no_low_liquidity < total:
        recommendations.append(f"建议对{total - no_low_liquidity}台低流动性车辆单独披露或拆包处置")
    if not recommendations:
        recommendations.append("资产包字段和估值质量较好，可进入买方询价或竞价流程")

    if level == "A":
        summary_text = "适合公开询价/竞价转让，资料和估值质量较好。"
    elif level == "B":
        summary_text = "适合定向邀约买方报价，可对少量瑕疵资产单独披露。"
    elif level == "C":
        summary_text = "建议补充资料后再出让，避免买方以字段缺失整体压价。"
    elif level == "D":
        summary_text = "建议拆包、剔除高风险资产或先完成资料修复。"
    else:
        summary_text = "不建议整体转让，优先考虑清收、诉讼、核销或小包处置。"

    return TradeabilityResult(
        score=score,
        level=level,
        summary=summary_text,
        recommendations=recommendations,
        breakdown=breakdown,
    )
