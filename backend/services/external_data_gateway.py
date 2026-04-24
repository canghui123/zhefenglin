"""Reserved external data gateway for vehicle-finance disposal signals.

The first version is intentionally provider-neutral: it normalizes signals and
returns deterministic rule scores. Real GPS/ETC/violation/judicial providers can
plug in behind this service without changing downstream decision logic.
"""

from typing import Optional

from models.external_data import (
    ExternalProviderCapability,
    FindCarSignalRequest,
    FindCarSignalResult,
    JudicialRiskRequest,
    JudicialRiskResult,
)


PROVIDERS = [
    ExternalProviderCapability(
        provider_code="gps_trace",
        provider_name="GPS轨迹线索",
        category="find_car",
        capabilities=["last_seen", "geo_fence", "signal_freshness"],
    ),
    ExternalProviderCapability(
        provider_code="etc_trace",
        provider_name="高速ETC线索",
        category="find_car",
        capabilities=["recent_toll_station", "travel_direction"],
    ),
    ExternalProviderCapability(
        provider_code="traffic_violation",
        provider_name="违章查询线索",
        category="find_car",
        capabilities=["recent_violation_city", "vehicle_activity"],
    ),
    ExternalProviderCapability(
        provider_code="judicial_risk",
        provider_name="司法风险线索",
        category="judicial",
        capabilities=["dishonest_enforced", "restricted_consumption", "litigation_count"],
    ),
]


def list_provider_capabilities() -> list[ExternalProviderCapability]:
    return PROVIDERS


def _freshness_points(
    days: Optional[int],
    *,
    fresh: int,
    stale: int,
    points: float,
) -> tuple[float, Optional[str]]:
    if days is None:
        return 0, None
    if days <= fresh:
        return points, f"{days}天内存在强线索"
    if days <= stale:
        return points * 0.55, f"{days}天内存在弱线索"
    return points * 0.20, f"{days}天前存在历史线索"


def compute_find_car_score(req: FindCarSignalRequest) -> FindCarSignalResult:
    score = 8.0
    signals: list[str] = []

    for value, fresh, stale, points, label in [
        (req.gps_recent_days, 3, 14, 45, "GPS"),
        (req.etc_recent_days, 7, 30, 25, "ETC"),
        (req.violation_recent_days, 14, 60, 18, "违章"),
    ]:
        delta, note = _freshness_points(value, fresh=fresh, stale=stale, points=points)
        score += delta
        if note:
            signals.append(f"{label}{note}")

    if req.city:
        score += 4
        signals.append(f"已定位到城市：{req.city}")
    elif req.province:
        score += 2
        signals.append(f"已定位到省份：{req.province}")

    if req.manual_hint:
        score += 5
        signals.append("存在人工补充线索")

    score = round(min(score, 100), 2)
    if score >= 70:
        level = "high"
        action = "建议优先派发收车工单，并同步准备竞拍/入库承接资源。"
    elif score >= 40:
        level = "medium"
        action = "建议补充核验线索后派单，避免无效拖车成本。"
    else:
        level = "low"
        action = "线索不足，建议先补充GPS/ETC/违章等外部数据再决定是否派单。"

    return FindCarSignalResult(
        score=score,
        level=level,
        signals=signals,
        recommended_action=action,
    )


def assess_judicial_risk(req: JudicialRiskRequest) -> JudicialRiskResult:
    score = min(req.litigation_count * 8, 40)
    tags: list[str] = []

    if req.dishonest_enforced:
        score += 45
        tags.append("失信被执行人")
    if req.restricted_consumption:
        score += 25
        tags.append("限制高消费")
    if req.litigation_count:
        tags.append(f"涉诉{req.litigation_count}起")

    score = round(min(score, 100), 2)
    collection_blocked = req.dishonest_enforced
    if score >= 70:
        level = "high"
    elif score >= 35:
        level = "medium"
    else:
        level = "low"

    if collection_blocked:
        note = "司法数据提示债务人为失信被执行人，系统将否决继续催收等待还款路径。"
    elif level == "high":
        note = "司法风险较高，建议优先评估诉讼/保全/车辆处置路径。"
    elif level == "medium":
        note = "司法风险中等，建议人工复核后再判断是否继续催收。"
    else:
        note = "未发现强司法阻断信号，可按常规路径评估。"

    return JudicialRiskResult(
        risk_level=level,
        score=score,
        collection_blocked=collection_blocked,
        risk_tags=tags,
        decision_note=note,
    )
