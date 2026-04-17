"""模块3：公司级不良资产经营驾驶舱API"""

from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.orm import Session

from dependencies.auth import get_current_user, require_role
from db.models.user import User
from db.session import get_db_session
from services.portfolio_engine import (
    generate_mock_portfolio,
    compute_strategy_comparison,
    compute_cashflow_projection,
)
from services import entitlement_service
from services.recommendation_engine import (
    get_executive_dashboard,
    get_manager_playbook,
    get_supervisor_console,
    get_action_center,
)

router = APIRouter(
    prefix="/api/portfolio",
    tags=["经营驾驶舱"],
    dependencies=[Depends(get_current_user)],
)

# 缓存mock数据（单次启动期间不变）
_cache = {}


def _get_portfolio():
    if "data" not in _cache:
        _cache["data"] = generate_mock_portfolio()
    return _cache["data"]


def _resolve_tenant_id_for_user(user: User) -> Optional[int]:
    return user.default_tenant_id


@router.get("/overview")
async def portfolio_overview():
    """组合总览"""
    data = _get_portfolio()
    ov = data["overview"]
    segments = data["segments"]

    # 补充建议区
    lr = ov["total_expected_loss_rate"]
    if lr > 0.50:
        judgment = "整体损失率超50%，经营压力极大，需立即启动应急处置方案"
    elif lr > 0.35:
        judgment = "整体损失率偏高，需加速处置并控制新增不良"
    else:
        judgment = "整体损失率可控，保持当前处置节奏，关注高风险分层"

    loss_sorted = sorted(segments, key=lambda s: s["expected_loss_amount"], reverse=True)
    top_risks = [
        f"{loss_sorted[0]['segment_name']}损失占比最高" if loss_sorted else "",
        f"高风险分层{ov['high_risk_segment_count']}个，需重点关注",
        f"平均库存{ov['avg_inventory_days']}天，贬值风险持续累积",
    ]
    top_actions = [
        "加速在库资产竞拍出清",
        "M4+资产启动法务推进",
        "评估未收回资产的收车ROI",
    ]

    # 图表数据
    bucket_dist = {}
    status_dist = {}
    for seg in segments:
        b = seg["overdue_bucket"]
        bucket_dist[b] = bucket_dist.get(b, 0) + seg["total_ead"]
        s = seg["recovered_status"]
        status_dist[s] = status_dist.get(s, 0) + seg["total_ead"]

    return {
        **ov,
        "monthly_judgment": judgment,
        "top_risks": [r for r in top_risks if r],
        "top_actions": top_actions,
        "resource_suggestions": [
            "评估收车团队产能是否匹配",
            "检查竞拍渠道承接能力",
            "确认法务预算是否充足",
        ],
        "charts": {
            "overdue_distribution": [{"bucket": k, "ead": round(v, 2)} for k, v in bucket_dist.items()],
            "status_distribution": [{"status": k, "ead": round(v, 2)} for k, v in status_dist.items()],
            "cashflow_trend": [
                {"period": "30天", "amount": ov["cash_30d"]},
                {"period": "90天", "amount": ov["cash_90d"]},
                {"period": "180天", "amount": ov["cash_180d"]},
            ],
        },
    }


@router.get("/segmentation")
async def portfolio_segmentation(
    dimension: str = Query("overdue_bucket", description="分层维度: overdue_bucket / recovered_status"),
):
    """分层分析"""
    data = _get_portfolio()
    segments = data["segments"]

    # 按维度汇总
    grouped = {}
    for seg in segments:
        key = seg.get(dimension, "其他")
        if key not in grouped:
            grouped[key] = {
                "dimension_value": key,
                "asset_count": 0,
                "total_ead": 0,
                "expected_loss_amount": 0,
                "cash_30d": 0,
                "cash_90d": 0,
                "cash_180d": 0,
                "sub_segments": [],
            }
        g = grouped[key]
        g["asset_count"] += seg["asset_count"]
        g["total_ead"] += seg["total_ead"]
        g["expected_loss_amount"] += seg["expected_loss_amount"]
        g["cash_30d"] += seg["cash_30d"]
        g["cash_90d"] += seg["cash_90d"]
        g["cash_180d"] += seg["cash_180d"]
        g["sub_segments"].append(seg)

    result = []
    for key, g in grouped.items():
        g["expected_loss_rate"] = round(g["expected_loss_amount"] / g["total_ead"], 4) if g["total_ead"] else 0
        g["total_ead"] = round(g["total_ead"], 2)
        g["expected_loss_amount"] = round(g["expected_loss_amount"], 2)
        g["cash_30d"] = round(g["cash_30d"], 2)
        g["cash_90d"] = round(g["cash_90d"], 2)
        g["cash_180d"] = round(g["cash_180d"], 2)
        result.append(g)

    total_ead = data["overview"]["total_ead"]
    total_loss = data["overview"]["total_expected_loss"]

    return {
        "dimension": dimension,
        "total_ead": total_ead,
        "total_loss": total_loss,
        "groups": result,
    }


@router.get("/strategies")
async def portfolio_strategies(
    segment_index: int = Query(0, description="分层索引(0-based)"),
):
    """处置路径模拟 — 对指定分层对比所有路径"""
    data = _get_portfolio()
    segments = data["segments"]

    if segment_index < 0 or segment_index >= len(segments):
        segment_index = 0

    seg = segments[segment_index]
    strategies = compute_strategy_comparison(seg)

    recommended = None
    for s in strategies:
        if not s["not_recommended_reasons"]:
            recommended = s["strategy_type"]
            break

    return {
        "segment_index": segment_index,
        "segment_name": seg["segment_name"],
        "segment_ead": seg["total_ead"],
        "segment_count": seg["asset_count"],
        "strategies": strategies,
        "recommended_strategy": recommended,
        "total_segments": len(segments),
        "segment_list": [{"index": i, "name": s["segment_name"]} for i, s in enumerate(segments)],
    }


@router.get("/cashflow")
async def portfolio_cashflow():
    """现金回流分析"""
    data = _get_portfolio()
    cf = compute_cashflow_projection(data["segments"])
    return {
        "snapshot_date": data["overview"]["snapshot_date"],
        "total_ead": data["overview"]["total_ead"],
        **cf,
    }


# ============ 管理智能决策 ============

@router.get("/executive", dependencies=[Depends(require_role("manager"))])
async def executive_dashboard(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """高管驾驶页"""
    tenant_id = _resolve_tenant_id_for_user(user)
    if tenant_id is not None:
        entitlement_service.ensure_feature_enabled(
            session, tenant_id=tenant_id, feature_key="portfolio.advanced_pages"
        )
    data = _get_portfolio()
    return get_executive_dashboard(data["overview"], data["segments"])


@router.get("/manager-playbook", dependencies=[Depends(require_role("manager"))])
async def manager_playbook(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_session),
):
    """经理作战手册"""
    tenant_id = _resolve_tenant_id_for_user(user)
    if tenant_id is not None:
        entitlement_service.ensure_feature_enabled(
            session, tenant_id=tenant_id, feature_key="portfolio.advanced_pages"
        )
    data = _get_portfolio()
    return get_manager_playbook(data["overview"], data["segments"])


@router.get("/supervisor-console", dependencies=[Depends(require_role("operator"))])
async def supervisor_console():
    """主管执行控制台"""
    data = _get_portfolio()
    return get_supervisor_console(data["overview"], data["segments"])


@router.get("/action-center", dependencies=[Depends(require_role("operator"))])
async def action_center():
    """动作中心"""
    data = _get_portfolio()
    return get_action_center(data["overview"], data["segments"])
