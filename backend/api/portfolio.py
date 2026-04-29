"""模块3：公司级不良资产经营驾驶舱API"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.session import get_db_session
from dependencies.auth import get_current_user, require_role
from repositories import data_import_repo, tenant_repo
from services.tenant_context import TENANT_HEADER
from services.portfolio_engine import (
    generate_empty_portfolio,
    generate_mock_portfolio,
    generate_portfolio_from_imports,
    compute_strategy_comparison,
    compute_cashflow_projection,
)
from services.recommendation_engine import (
    build_action_work_order_candidates,
    find_segment_by_name,
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


class PortfolioSourceSelection(BaseModel):
    batch_ids: list[int] = Field(..., min_length=1)


def get_optional_portfolio_tenant_id(
    request: Request,
    user=Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> Optional[int]:
    """Resolve tenant for import-backed analytics, but keep legacy demo access.

    Some old accounts/tests were created before tenant membership existed. For
    those users we still allow the mock portfolio, while real tenant users get
    isolated customer-import analytics.
    """
    requested_code = request.headers.get(TENANT_HEADER)
    if requested_code:
        tenant = tenant_repo.get_tenant_by_code(session, requested_code.strip())
        if tenant is None:
            raise HTTPException(status_code=404, detail="租户不存在")
        if not tenant_repo.has_membership(
            session, user_id=user.id, tenant_id=tenant.id
        ):
            raise HTTPException(status_code=403, detail="无权访问该租户")
        return tenant.id
    return user.default_tenant_id


def _get_portfolio(session: Optional[Session] = None, tenant_id: Optional[int] = None):
    if isinstance(session, Session) and isinstance(tenant_id, int):
        imported = generate_portfolio_from_imports(session, tenant_id=tenant_id)
        if imported is not None:
            return imported
        if data_import_repo.has_any_batch(
            session,
            tenant_id=tenant_id,
            import_type="asset_ledger",
        ):
            return generate_empty_portfolio()
    if "mock" not in _cache:
        _cache["mock"] = generate_mock_portfolio()
    return _cache["mock"]


@router.post("/source/clear", dependencies=[Depends(require_role("operator"))])
async def clear_portfolio_source(
    session: Session = Depends(get_db_session),
    tenant_id: Optional[int] = Depends(get_optional_portfolio_tenant_id),
):
    """清空当前组合分析数据源，保留历史导入批次和行明细。"""
    if tenant_id is None:
        raise HTTPException(status_code=403, detail="未配置默认租户")
    cleared = data_import_repo.archive_active_batches(
        session,
        tenant_id=tenant_id,
        import_type="asset_ledger",
    )
    return {
        "data_source": "empty",
        "cleared_batches": cleared,
        "message": "已清空当前组合分析数据源，历史导入批次和明细仍保留",
    }


@router.post("/source/select", dependencies=[Depends(require_role("operator"))])
async def select_portfolio_source(
    payload: PortfolioSourceSelection,
    session: Session = Depends(get_db_session),
    tenant_id: Optional[int] = Depends(get_optional_portfolio_tenant_id),
):
    """选择一个或多个导入批次作为组合分析数据源。"""
    if tenant_id is None:
        raise HTTPException(status_code=403, detail="未配置默认租户")
    batch_ids = list(dict.fromkeys(payload.batch_ids))
    batches = data_import_repo.list_source_batches_by_ids(
        session,
        tenant_id=tenant_id,
        batch_ids=batch_ids,
        import_type="asset_ledger",
    )
    found_ids = {batch.id for batch in batches}
    missing_ids = [batch_id for batch_id in batch_ids if batch_id not in found_ids]
    if missing_ids:
        raise HTTPException(
            status_code=400,
            detail=f"以下批次不能作为组合分析数据源: {missing_ids}",
        )
    activated = data_import_repo.activate_batches_as_source(
        session,
        tenant_id=tenant_id,
        batch_ids=batch_ids,
        import_type="asset_ledger",
    )
    return {
        "data_source": "customer_import",
        "active_batch_ids": batch_ids,
        "active_batches": activated,
        "message": f"已将 {activated} 个批次设为组合分析数据源",
    }


@router.get("/overview")
async def portfolio_overview(
    session: Session = Depends(get_db_session),
    tenant_id: Optional[int] = Depends(get_optional_portfolio_tenant_id),
):
    """组合总览"""
    data = _get_portfolio(session, tenant_id)
    ov = data["overview"]
    segments = data["segments"]

    # 补充建议区
    lr = ov["total_expected_loss_rate"]
    if ov.get("data_source") == "empty":
        judgment = "当前没有启用的客户资产台账，请先在数据接入中心上传新的资产/逾期表格"
    elif lr > 0.50:
        judgment = "整体损失率超50%，经营压力极大，需立即启动应急处置方案"
    elif lr > 0.35:
        judgment = "整体损失率偏高，需加速处置并控制新增不良"
    else:
        judgment = "整体损失率可控，保持当前处置节奏，关注高风险分层"

    loss_sorted = sorted(segments, key=lambda s: s["expected_loss_amount"], reverse=True)
    if ov.get("data_source") == "empty":
        top_risks = ["暂无活跃数据源，所有经营分析暂不可用"]
        top_actions = ["上传新的资产/逾期台账", "确认可用行和错误行", "刷新组合总览查看新分析"]
    else:
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
        "resource_suggestions": (
            ["先完成客户资产台账上传，再生成资源配置建议"]
            if ov.get("data_source") == "empty"
            else [
                "评估收车团队产能是否匹配",
                "检查竞拍渠道承接能力",
                "确认法务预算是否充足",
            ]
        ),
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
    session: Session = Depends(get_db_session),
    tenant_id: Optional[int] = Depends(get_optional_portfolio_tenant_id),
):
    """分层分析"""
    data = _get_portfolio(session, tenant_id)
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
    session: Session = Depends(get_db_session),
    tenant_id: Optional[int] = Depends(get_optional_portfolio_tenant_id),
):
    """处置路径模拟 — 对指定分层对比所有路径"""
    data = _get_portfolio(session, tenant_id)
    segments = data["segments"]

    if not segments:
        return {
            "segment_index": 0,
            "segment_name": "暂无数据",
            "segment_ead": 0,
            "segment_count": 0,
            "strategies": [],
            "recommended_strategy": None,
            "total_segments": 0,
            "segment_list": [],
        }

    if segment_index < 0 or segment_index >= len(segments):
        segment_index = 0

    seg = segments[segment_index]
    strategies = compute_strategy_comparison(seg)

    # 2026-04-22 产品决策：不再由系统做"推荐路径"判定 ——
    # 业务规则过于复杂（物权、入库、法务资源、客户关系等），人工判断更靠谱。
    # 前端仍展示每条路径的成本/净回收/损失率等完整数据以及约束提示，
    # recommended_strategy 字段保留但固定为 None，避免打破既有前端契约。
    return {
        "segment_index": segment_index,
        "segment_name": seg["segment_name"],
        "segment_ead": seg["total_ead"],
        "segment_count": seg["asset_count"],
        "strategies": strategies,
        "recommended_strategy": None,
        "total_segments": len(segments),
        "segment_list": [{"index": i, "name": s["segment_name"]} for i, s in enumerate(segments)],
    }


@router.get("/cashflow")
async def portfolio_cashflow(
    session: Session = Depends(get_db_session),
    tenant_id: Optional[int] = Depends(get_optional_portfolio_tenant_id),
):
    """现金回流分析"""
    data = _get_portfolio(session, tenant_id)
    cf = compute_cashflow_projection(data["segments"])
    return {
        "snapshot_date": data["overview"]["snapshot_date"],
        "total_ead": data["overview"]["total_ead"],
        **cf,
    }


# ============ 管理智能决策 ============

@router.get("/executive", dependencies=[Depends(require_role("manager"))])
async def executive_dashboard(
    session: Session = Depends(get_db_session),
    tenant_id: Optional[int] = Depends(get_optional_portfolio_tenant_id),
):
    """高管驾驶页"""
    data = _get_portfolio(session, tenant_id)
    return get_executive_dashboard(data["overview"], data["segments"])


@router.get("/manager-playbook", dependencies=[Depends(require_role("manager"))])
async def manager_playbook(
    session: Session = Depends(get_db_session),
    tenant_id: Optional[int] = Depends(get_optional_portfolio_tenant_id),
):
    """经理作战手册"""
    data = _get_portfolio(session, tenant_id)
    return get_manager_playbook(data["overview"], data["segments"])


@router.get("/supervisor-console", dependencies=[Depends(require_role("operator"))])
async def supervisor_console(
    session: Session = Depends(get_db_session),
    tenant_id: Optional[int] = Depends(get_optional_portfolio_tenant_id),
):
    """主管执行控制台"""
    data = _get_portfolio(session, tenant_id)
    return get_supervisor_console(data["overview"], data["segments"])


@router.get("/action-center", dependencies=[Depends(require_role("operator"))])
async def action_center(
    session: Session = Depends(get_db_session),
    tenant_id: Optional[int] = Depends(get_optional_portfolio_tenant_id),
):
    """动作中心"""
    data = _get_portfolio(session, tenant_id)
    return get_action_center(data["overview"], data["segments"])


@router.get("/action-center/candidates", dependencies=[Depends(require_role("operator"))])
async def action_center_candidates(
    order_type: str = Query(..., description="工单类型: towing / auction_push"),
    segment_name: str = Query(..., description="动作中心分层名称"),
    session: Session = Depends(get_db_session),
    tenant_id: Optional[int] = Depends(get_optional_portfolio_tenant_id),
):
    """按动作中心分层展开候选车辆，用于批量编排拖车/拍卖工单。"""
    if order_type not in {"towing", "auction_push"}:
        raise HTTPException(status_code=400, detail="order_type 仅支持 towing / auction_push")
    data = _get_portfolio(session, tenant_id)
    segment = find_segment_by_name(data["segments"], segment_name)
    if segment is None:
        raise HTTPException(status_code=404, detail="未找到对应分层")
    return build_action_work_order_candidates(segment, order_type=order_type)
