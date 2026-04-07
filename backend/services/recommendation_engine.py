"""角色建议引擎 — 基于规则为不同角色生成建议"""

from services.portfolio_engine import (
    generate_role_recommendations,
    STRATEGY_TYPES,
)


def get_executive_dashboard(overview: dict, segments: list) -> dict:
    """生成高管驾驶页数据"""
    recommendations = generate_role_recommendations(overview, segments, "executive")

    loss_sorted = sorted(segments, key=lambda s: s["expected_loss_amount"], reverse=True)
    loss_contribution = []
    for seg in loss_sorted[:10]:
        pct = seg["expected_loss_amount"] / overview["total_expected_loss"] * 100 if overview["total_expected_loss"] else 0
        loss_contribution.append({
            "segment_name": seg["segment_name"],
            "loss_amount": round(seg["expected_loss_amount"], 2),
            "loss_rate": round(seg["expected_loss_rate"], 4),
            "contribution_pct": round(pct, 2),
            "cash_30d": round(seg["cash_30d"], 2),
        })

    inv_count = sum(s["asset_count"] for s in segments if s["recovered_status"] == "已入库")
    not_rec = sum(s["asset_count"] for s in segments if s["recovered_status"] == "未收回")

    resource_suggestions = []
    if not_rec > inv_count * 2:
        resource_suggestions.append("建议增配收车团队资源，未收回车辆是已入库的2倍以上")
    m4p = [s for s in segments if any(x in s.get("overdue_bucket", "") for x in ("M4", "M5", "M6"))]
    if sum(s["asset_count"] for s in m4p) > 50:
        resource_suggestions.append("建议增加法务预算，M4+资产超50笔需加速法务推进")
    if inv_count > 30:
        resource_suggestions.append("建议优先出清长库龄库存，减少贬值和资金占用")
    resource_suggestions.append("建议评估竞拍渠道承接能力，确保出清节奏匹配")

    approval_items = []
    if overview.get("total_expected_loss", 0) > 5000000:
        approval_items.append("预计总损失超500万，建议启动专项处置方案审批")
    if len(m4p) > 5:
        approval_items.append("M4+分层数量较多，建议审批批量法务推进方案")

    return {
        "overview": overview,
        "loss_contribution_by_segment": loss_contribution,
        "resource_suggestions": resource_suggestions,
        "approval_items": approval_items,
        "recommendations": recommendations,
    }


def get_manager_playbook(overview: dict, segments: list) -> dict:
    """生成经理作战手册"""
    recommendations = generate_role_recommendations(overview, segments, "manager")

    kpis = [
        {
            "name": "现金回流目标",
            "recommended_value": round(overview["cash_30d"], 2),
            "unit": "元/月",
            "historical_avg": round(overview["cash_30d"] * 0.85, 2),
            "achievable_value": round(overview["cash_30d"] * 0.95, 2),
            "risk_note": "需确保竞拍渠道畅通",
        },
        {
            "name": "收车率目标",
            "recommended_value": round(overview.get("recovered_rate", 0) + 0.05, 4),
            "unit": "%",
            "historical_avg": round(overview.get("recovered_rate", 0), 4),
            "achievable_value": round(overview.get("recovered_rate", 0) + 0.03, 4),
            "risk_note": "GPS离线车辆拖回难度大",
        },
        {
            "name": "库存压降目标",
            "recommended_value": 15,
            "unit": "台/月",
            "historical_avg": 10,
            "achievable_value": 12,
            "risk_note": "需评估渠道承接能力",
        },
    ]

    weekly_rhythm = [
        {"week": 1, "focus": "筛选与启动", "actions": ["完成分层分析", "确定处置优先级", "分配任务"]},
        {"week": 2, "focus": "重点推进", "actions": ["推进高优先级收车", "法务资料准备", "在库资产定价"]},
        {"week": 3, "focus": "法务/竞拍/出清", "actions": ["法务案件提交", "竞拍上架", "长库龄出清"]},
        {"week": 4, "focus": "冲刺/纠偏/复盘", "actions": ["目标冲刺", "偏差分析", "下月计划"]},
    ]

    return {
        "recommendations": recommendations,
        "kpis": kpis,
        "weekly_rhythm": weekly_rhythm,
    }


def get_supervisor_console(overview: dict, segments: list) -> dict:
    """生成主管执行控制台"""
    recommendations = generate_role_recommendations(overview, segments, "supervisor")

    high_priority_pool = []
    for seg in sorted(segments, key=lambda s: s["expected_loss_amount"], reverse=True)[:5]:
        high_priority_pool.append({
            "segment_name": seg["segment_name"],
            "status": seg["recovered_status"],
            "next_action": STRATEGY_TYPES.get(seg.get("recommended_strategy", "collection"), "催收"),
            "urgency": "高" if seg["expected_loss_rate"] > 0.5 else "中",
            "loss_impact": round(seg["expected_loss_amount"], 2),
            "cash_impact": round(seg["cash_30d"], 2),
        })

    return {
        "recommendations": recommendations,
        "high_priority_pool": high_priority_pool,
    }


def get_action_center(overview: dict, segments: list) -> dict:
    """生成动作中心（执行层）"""
    recommendations = generate_role_recommendations(overview, segments, "operator")

    inv_segs = [s for s in segments if s["recovered_status"] == "已入库"]
    auction_ready = []
    for seg in inv_segs[:5]:
        auction_ready.append({
            "segment_name": seg["segment_name"],
            "count": seg["asset_count"],
            "estimated_value": round(seg["avg_vehicle_value"] * seg["asset_count"], 2),
            "recommended_floor_price": round(seg["avg_vehicle_value"] * 0.85, 2),
            "risk_tags": ["库龄偏长"] if seg.get("avg_recovery_days", 0) > 60 else [],
        })

    recovery_segs = [s for s in segments if s["recovered_status"] == "未收回"]
    recovery_tasks = []
    for seg in recovery_segs[:5]:
        recovery_tasks.append({
            "segment_name": seg["segment_name"],
            "count": seg["asset_count"],
            "overdue_bucket": seg["overdue_bucket"],
            "total_ead": round(seg["total_ead"], 2),
        })

    return {
        "recommendations": recommendations,
        "auction_ready": auction_ready,
        "recovery_tasks": recovery_tasks,
    }
