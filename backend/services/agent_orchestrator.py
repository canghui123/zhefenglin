"""First-stage AI command center orchestration.

The orchestrator owns Agent routing, data collection, fallback output and
persistence. Frontend callers never talk to an LLM directly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import settings
from db.models.agent import AgentRun
from db.models.asset_package import Asset, AssetPackage
from db.models.role import role_rank
from db.models.valuation_control import ApprovalRequest
from db.models.work_order import WorkOrder
from models.ai_command import (
    AgentEvidence,
    AgentOutput,
    AgentRunCreate,
    AgentRunOut,
    AgentTaskOut,
    AgentRecommendationOut,
    AgentWorkbenchItem,
    AiCommandOverview,
)
from models.asset import PackageCalculationResult
from models.portfolio import PortfolioCapacityPlan
from repositories import (
    agent_repo,
    asset_package_repo,
    plan_repo,
    portfolio_repo,
    subscription_repo,
    usage_repo,
)
from services.buyer_offer_analysis import analyze_buyer_offer
from services.portfolio_capacity_planner import build_capacity_plan, get_capacity_settings


AGENT_CATALOG: dict[str, dict[str, str]] = {
    "asset_package_diagnosis_agent": {
        "name": "资产包解读 Agent",
        "stage": "phase_1",
        "status": "rules_based",
        "min_role": "operator",
    },
    "valuation_analysis_agent": {
        "name": "估值分析 Agent",
        "stage": "phase_1",
        "status": "rules_based",
        "min_role": "operator",
    },
    "pricing_strategy_agent": {
        "name": "定价策略 Agent",
        "stage": "phase_1",
        "status": "rules_based",
        "min_role": "manager",
    },
    "buyer_offer_analysis_agent": {
        "name": "买方报价反推 Agent",
        "stage": "phase_1",
        "status": "rules_based",
        "min_role": "operator",
    },
    "operation_planning_agent": {
        "name": "运营计划 Agent",
        "stage": "phase_2",
        "status": "rules_based",
        "min_role": "manager",
    },
    "task_generation_agent": {
        "name": "任务生成 Agent",
        "stage": "phase_2",
        "status": "rules_based",
        "min_role": "manager",
    },
    "report_generation_agent": {
        "name": "报告生成 Agent",
        "stage": "phase_2",
        "status": "rules_based",
        "min_role": "manager",
    },
    "cost_control_agent": {
        "name": "成本控制 Agent",
        "stage": "phase_2",
        "status": "rules_based",
        "min_role": "admin",
    },
}


SUGGESTED_PROMPTS = [
    "分析这个资产包适不适合整体出让",
    "找出最应该优先竞拍的车辆",
    "买方报价是否合理",
    "生成本周处置作战计划",
    "哪些车辆需要补资料",
    "预测未来 90 天现金流",
]


@dataclass
class PackageContext:
    package: Optional[AssetPackage]
    assets: list[Asset]
    result: Optional[PackageCalculationResult]


@dataclass
class PortfolioContext:
    snapshot_id: Optional[int]
    snapshot_date: Optional[str]
    segments: list[dict[str, Any]]
    capacity_plan: Optional[PortfolioCapacityPlan]
    empty_reason: Optional[str] = None


def _loads(value: Optional[str]) -> dict[str, Any]:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _parse_result(value: Optional[str]) -> Optional[PackageCalculationResult]:
    if not value:
        return None
    try:
        return PackageCalculationResult.model_validate_json(value)
    except Exception:
        return None


def classify_intent(question: str) -> str:
    text = (question or "").lower()
    if any(keyword in text for keyword in ("报价", "offer", "买方", "压价")):
        return "buyer_offer_analysis_agent"
    if any(keyword in text for keyword in ("估值", "车300", "valuation", "覆盖")):
        return "valuation_analysis_agent"
    if any(keyword in text for keyword in ("定价", "出让", "折扣", "价格", "转让")):
        return "pricing_strategy_agent"
    if any(keyword in text for keyword in ("计划", "本周", "90 天", "90天", "现金流")):
        return "operation_planning_agent"
    if any(keyword in text for keyword in ("任务", "补资料", "派单")):
        return "task_generation_agent"
    return "asset_package_diagnosis_agent"


def _latest_package_context(
    session: Session,
    *,
    tenant_id: int,
    asset_package_id: Optional[int],
) -> PackageContext:
    package = None
    if asset_package_id:
        package = asset_package_repo.get_package_by_id(session, asset_package_id, tenant_id=tenant_id)
    else:
        packages = asset_package_repo.list_packages(session, tenant_id=tenant_id)
        package = packages[0] if packages else None

    if package is None:
        return PackageContext(package=None, assets=[], result=None)

    assets = asset_package_repo.list_assets_for_package(
        session,
        package_id=package.id,
        tenant_id=tenant_id,
    )
    return PackageContext(
        package=package,
        assets=assets,
        result=_parse_result(package.results_json),
    )


def _portfolio_context(session: Session, *, tenant_id: int) -> PortfolioContext:
    settings = get_capacity_settings(session, tenant_id)
    snapshot = portfolio_repo.get_latest_snapshot_for_tenant(session, tenant_id)
    if snapshot is None:
        return PortfolioContext(
            snapshot_id=None,
            snapshot_date=None,
            segments=[],
            capacity_plan=PortfolioCapacityPlan(
                settings=settings,
                data_source="empty",
                empty_reason="暂无真实组合数据，无法生成运营计划",
                summary="暂无真实组合数据，无法生成运营计划",
            ),
            empty_reason="暂无真实组合数据，无法生成运营计划",
        )

    rows = portfolio_repo.list_snapshot_segment_metrics(
        session,
        snapshot_id=snapshot.id,
        tenant_id=tenant_id,
    )
    segments = portfolio_repo.build_capacity_segments(rows)
    capacity_plan = build_capacity_plan(segments, settings) if segments else PortfolioCapacityPlan(
        settings=settings,
        data_source="empty",
        snapshot_id=snapshot.id,
        snapshot_date=snapshot.snapshot_date,
        empty_reason="当前组合快照暂无可用于运营计划的分层数据",
        summary="当前组合快照暂无可用于运营计划的分层数据",
    )
    return PortfolioContext(
        snapshot_id=snapshot.id,
        snapshot_date=snapshot.snapshot_date,
        segments=segments,
        capacity_plan=capacity_plan.model_copy(
            update={
                "data_source": "real_portfolio" if segments else "empty",
                "snapshot_id": snapshot.id,
                "snapshot_date": snapshot.snapshot_date,
                "segment_count": len(segments),
                "asset_count": sum(int(segment.get("asset_count") or 0) for segment in segments),
                "generated_at": datetime.utcnow().isoformat(),
            }
        ),
        empty_reason=None if segments else "当前组合快照暂无可用于运营计划的分层数据",
    )


def _agent_status_evidence(agent_type: str) -> AgentEvidence:
    info = AGENT_CATALOG[agent_type]
    return AgentEvidence(
        source="agent_catalog",
        label="status",
        value=info["status"],
        evidence_source="agent_catalog",
        related_object_type="agent_type",
        related_object_id=agent_type,
        calculation_basis="Agent 目录状态",
        data_quality_notes="rules_based 表示确定性规则输出，仍需人工复核",
    )


def _base_evidence(context: PackageContext) -> list[AgentEvidence]:
    evidence = [
        AgentEvidence(
            source="agent_orchestrator",
            label="llm_fallback",
            value=not bool(settings.deepseek_api_key),
            evidence_source="agent_orchestrator",
            related_object_type="agent_run",
            calculation_basis="根据运行环境是否配置 DeepSeek API Key 判断是否进入 fallback 输出",
            data_quality_notes="fallback=true 表示当前输出未调用外部 LLM",
        )
    ]
    if context.package is not None:
        evidence.extend(
            [
                AgentEvidence(
                    source="asset_packages",
                    label="package_id",
                    value=context.package.id,
                    evidence_source="asset_packages",
                    related_object_type="asset_package",
                    related_object_id=str(context.package.id),
                    calculation_basis="按当前租户资产包读取",
                ),
                AgentEvidence(
                    source="asset_packages",
                    label="total_assets",
                    value=context.package.total_assets,
                    evidence_source="asset_packages",
                    related_object_type="asset_package",
                    related_object_id=str(context.package.id),
                    calculation_basis="资产包台账总数",
                ),
            ]
        )
    return evidence


def _asset_counts(assets: list[Asset]) -> dict[str, int]:
    return {
        "asset_count": len(assets),
        "missing_valuation_count": sum(1 for row in assets if row.che300_valuation is None),
        "gps_offline_count": sum(1 for row in assets if row.gps_online == 0),
        "insurance_lapsed_count": sum(1 for row in assets if row.insurance_lapsed == 1),
        "ownership_pending_count": sum(1 for row in assets if row.ownership_transferred == 0),
    }


def _confidence_from_coverage(total: int, missing: int) -> float:
    if total <= 0:
        return 0.35
    coverage = max(0, total - missing) / total
    return round(min(0.92, max(0.4, 0.45 + coverage * 0.45)), 2)


def _diagnose_asset_package(context: PackageContext) -> AgentOutput:
    evidence = _base_evidence(context)
    if context.package is None:
        return AgentOutput(
            summary="当前租户暂无可诊断资产包，AI 指挥中心已进入空数据安全模式。",
            key_findings=["未找到资产包记录"],
            recommended_actions=["先上传资产包 Excel 并完成字段识别与估值"],
            risk_warnings=["无底层资产数据时不得生成出让或处置结论"],
            confidence_score=0.35,
            evidence=evidence,
            requires_human_review=True,
        )

    counts = _asset_counts(context.assets)
    risk_items = counts["gps_offline_count"] + counts["insurance_lapsed_count"] + counts["ownership_pending_count"]
    findings = [
        f"资产包共 {context.package.total_assets or counts['asset_count']} 台，已读取 {counts['asset_count']} 台明细。",
        f"缺少估值车辆 {counts['missing_valuation_count']} 台。",
        f"GPS 离线、脱保或权属未完成等基础风险合计 {risk_items} 项。",
    ]
    warnings: list[str] = []
    if counts["missing_valuation_count"]:
        warnings.append("存在估值缺口，整体出让前应补齐关键车辆估值依据")
    if risk_items:
        warnings.append("存在基础资料或车辆状态风险，买方可能据此压价")
    if context.result and context.result.summary.risk_alerts:
        warnings.extend(context.result.summary.risk_alerts[:3])

    actions = [
        "对估值缺失、GPS 离线、脱保、权属未完成车辆建立补资料清单",
        "优先复核高本金或高估值偏差车辆，避免整体包被低估",
        "将 AI 结论作为出让沟通草稿，正式处置仍需经理复核",
    ]
    return AgentOutput(
        summary=f"{context.package.name or '最新资产包'} 已完成第一阶段资产包诊断，建议先处理数据缺口再进入正式出让决策。",
        key_findings=findings,
        recommended_actions=actions,
        risk_warnings=warnings or ["暂未识别重大数据风险，但仍需人工复核底层资产真实性"],
        confidence_score=_confidence_from_coverage(counts["asset_count"], counts["missing_valuation_count"]),
        evidence=evidence + [AgentEvidence(source="assets", label="risk_counts", value=counts)],
        requires_human_review=True,
    )


def _analyze_valuation(context: PackageContext) -> AgentOutput:
    evidence = _base_evidence(context)
    if context.package is None:
        return AgentOutput(
            summary="暂无资产包，无法进行估值覆盖分析。",
            key_findings=["未找到可分析的资产包"],
            recommended_actions=["先上传资产包并完成车300或 mock 估值"],
            risk_warnings=["不得在无估值依据时形成价格判断"],
            confidence_score=0.3,
            evidence=evidence,
            requires_human_review=True,
        )

    counts = _asset_counts(context.assets)
    valued_assets = [row for row in context.assets if row.che300_valuation is not None]
    total_value = sum(float(row.che300_valuation or 0) for row in valued_assets)
    total_principal = sum(float(row.loan_principal or 0) for row in context.assets)
    coverage_rate = (len(valued_assets) / counts["asset_count"]) if counts["asset_count"] else 0
    collateral_ratio = (total_value / total_principal) if total_principal > 0 else None
    findings = [
        f"估值覆盖率 {coverage_rate:.0%}，已估值 {len(valued_assets)} 台。",
        f"车300/估值合计约 {total_value:,.0f} 元。",
    ]
    if collateral_ratio is not None:
        findings.append(f"抵押物价值覆盖本金比例约 {collateral_ratio:.1%}。")

    warnings = []
    if coverage_rate < 0.8:
        warnings.append("估值覆盖率不足 80%，价格区间置信度受限")
    if collateral_ratio is not None and collateral_ratio < 0.7:
        warnings.append("抵押物价值覆盖偏低，需关注债权回收缺口")
    return AgentOutput(
        summary="估值分析已完成，当前结论仅用于风险识别和估值复核排期。",
        key_findings=findings,
        recommended_actions=[
            "优先补齐高本金车辆估值",
            "对估值异常低或缺失车辆发起人工复核",
            "将估值覆盖率作为报价谈判前置门槛",
        ],
        risk_warnings=warnings or ["估值覆盖暂无明显异常，仍需核查估值来源和车辆状态"],
        confidence_score=_confidence_from_coverage(counts["asset_count"], counts["missing_valuation_count"]),
        evidence=evidence
        + [
            AgentEvidence(source="assets", label="valuation_coverage_rate", value=round(coverage_rate, 4)),
            AgentEvidence(source="assets", label="collateral_coverage_ratio", value=collateral_ratio),
        ],
        requires_human_review=True,
    )


def _analyze_pricing(context: PackageContext) -> AgentOutput:
    evidence = _base_evidence(context)
    if context.result is None:
        return AgentOutput(
            summary="当前资产包尚未形成定价结果，无法给出完整价格策略。",
            key_findings=["未找到资产包定价计算结果"],
            recommended_actions=["先在资产包定价页完成一次定价计算", "保留人工审批作为正式出让前置条件"],
            risk_warnings=["不得仅凭资产包原始数据接受买方报价或批准出让"],
            confidence_score=0.42,
            evidence=evidence,
            requires_human_review=True,
        )

    summary = context.result.summary
    findings = [
        f"推荐出让中位价约 {summary.recommended_transfer_price_mid:,.0f} 元。",
        f"建议价格区间 {summary.recommended_transfer_price_low:,.0f} - {summary.recommended_transfer_price_high:,.0f} 元。",
        f"可交易性等级 {summary.tradeability_level}，评分 {summary.tradeability_score}。",
    ]
    warnings = list(summary.risk_alerts[:4])
    if summary.tradeability_level in {"D", "E"}:
        warnings.append("可交易性偏弱，不建议直接整体出让")
    return AgentOutput(
        summary="定价策略 Agent 已生成出让谈判草案，正式价格仍需审批确认。",
        key_findings=findings,
        recommended_actions=[
            "以中位价作为内部谈判锚点，低价成交必须说明风险折价依据",
            "对低流动性或资料缺口车辆考虑拆包",
            "正式报价、出让审批和合同确认必须走人工流程",
        ],
        risk_warnings=warnings or ["定价结果暂无重大风险预警，仍需复核参数和审批权限"],
        confidence_score=0.78,
        evidence=evidence
        + [
            AgentEvidence(source="asset_packages.results_json", label="recommended_transfer_price_mid", value=summary.recommended_transfer_price_mid),
            AgentEvidence(source="asset_packages.results_json", label="tradeability_level", value=summary.tradeability_level),
        ],
        requires_human_review=True,
    )


def _analyze_buyer_offer(context: PackageContext, request: AgentRunCreate) -> AgentOutput:
    evidence = _base_evidence(context)
    if context.result is None or request.buyer_offer_price is None:
        return AgentOutput(
            summary="买方报价分析需要先完成资产包定价，并录入买方报价金额。",
            key_findings=["缺少定价结果或买方报价"],
            recommended_actions=["补充 buyer_offer_price 后重新运行买方报价反推 Agent"],
            risk_warnings=["Agent 不得自动接受买方报价"],
            confidence_score=0.4,
            evidence=evidence,
            requires_human_review=True,
        )

    analysis = analyze_buyer_offer(
        context.result,
        buyer_offer_price=request.buyer_offer_price,
        buyer_offer_note=request.buyer_offer_note,
    )
    warnings = ["买方报价只能作为谈判输入，Agent 不得自动接受买方报价"]
    if analysis.buyer_offer_gap_rate is not None and analysis.buyer_offer_gap_rate > 0.1:
        warnings.append("买方报价低于系统建议价超过 10%，需经理复核")
    return AgentOutput(
        summary=analysis.buyer_offer_assessment,
        key_findings=[
            f"买方报价 {analysis.buyer_offer_price:,.0f} 元。",
            f"相对系统中位建议差额 {analysis.buyer_offer_gap:,.0f} 元。",
            f"报价折扣率 {analysis.buyer_offer_discount:.1%}" if analysis.buyer_offer_discount is not None else "报价折扣率暂不可计算。",
        ],
        recommended_actions=analysis.negotiation_suggestions,
        risk_warnings=warnings,
        confidence_score=0.76 if analysis.buyer_offer_gap_rate is not None else 0.45,
        evidence=evidence
        + [
            AgentEvidence(source="buyer_offer", label="buyer_offer_price", value=analysis.buyer_offer_price),
            AgentEvidence(source="buyer_offer", label="buyer_offer_gap_rate", value=analysis.buyer_offer_gap_rate),
        ],
        requires_human_review=True,
    )


def _segment_label(segment: dict[str, Any]) -> str:
    return str(segment.get("segment_name") or segment.get("name") or "未命名分层")


def _top_segments(
    segments: list[dict[str, Any]],
    key: str,
    *,
    limit: int = 5,
    reverse: bool = True,
) -> list[dict[str, Any]]:
    return sorted(
        segments,
        key=lambda row: float(row.get(key) or 0),
        reverse=reverse,
    )[:limit]


def _operation_plan_payload(portfolio: PortfolioContext, package: PackageContext) -> dict[str, Any]:
    segments = portfolio.segments
    capacity = portfolio.capacity_plan
    high_priority = _top_segments(segments, "expected_loss_amount", limit=5)
    auction_pool = [
        item.model_dump()
        for item in ((capacity.current_month_execution_plan if capacity else [])[:5])
        if item.task_type == "auction"
    ]
    legal_pool = [
        item.model_dump()
        for item in ((capacity.current_month_execution_plan if capacity else [])[:5])
        if item.task_type in {"litigation", "special_procedure"}
    ]
    data_pool = []
    if package.package is not None:
        counts = _asset_counts(package.assets)
        if counts["missing_valuation_count"] or counts["gps_offline_count"] or counts["ownership_pending_count"]:
            data_pool.append(
                {
                    "package_id": package.package.id,
                    "package_name": package.package.name,
                    "missing_valuation_count": counts["missing_valuation_count"],
                    "gps_offline_count": counts["gps_offline_count"],
                    "ownership_pending_count": counts["ownership_pending_count"],
                }
            )
    paused_pool = [item.model_dump() for item in (capacity.paused_pool if capacity else [])[:5]]
    deferred_pool = [item.model_dump() for item in (capacity.next_month_deferred_pool if capacity else [])[:5]]
    return {
        "weekly_focus": [
            "优先处理高损失贡献分层",
            "将可竞拍资产池推进至资料复核和底价确认",
            "对估值缺口、权属未完结和 GPS 离线资产补齐资料",
        ],
        "high_priority_asset_pool": [
            {
                "segment_name": _segment_label(segment),
                "asset_count": int(segment.get("asset_count") or 0),
                "expected_loss_amount": float(segment.get("expected_loss_amount") or 0),
                "cash_90d": float(segment.get("cash_90d") or 0),
                "recommended_strategy": segment.get("recommended_strategy"),
            }
            for segment in high_priority
        ],
        "auction_pool": auction_pool,
        "legal_pool": legal_pool,
        "data_completion_pool": data_pool,
        "paused_pool": paused_pool,
        "deferred_pool": deferred_pool,
        "capacity_bottlenecks": capacity.capacity_bottlenecks if capacity else [],
        "cashflow_focus": {
            "cash_30d": sum(float(segment.get("cash_30d") or 0) for segment in segments),
            "cash_90d": sum(float(segment.get("cash_90d") or 0) for segment in segments),
            "cash_180d": sum(float(segment.get("cash_180d") or 0) for segment in segments),
        },
    }


def _operation_planning_agent(package: PackageContext, portfolio: PortfolioContext) -> AgentOutput:
    evidence = _base_evidence(package)
    if portfolio.empty_reason and not portfolio.segments and package.package is None:
        return AgentOutput(
            summary="暂无真实组合数据和资产包数据，运营计划 Agent 已进入空数据安全模式。",
            key_findings=["未找到真实组合快照或资产包"],
            recommended_actions=["先导入组合数据或上传资产包，再生成本周作战计划"],
            risk_warnings=["无底层资产与产能数据时不得形成正式运营排期"],
            confidence_score=0.35,
            evidence=evidence + [_agent_status_evidence("operation_planning_agent")],
            requires_human_review=True,
        )

    plan = _operation_plan_payload(portfolio, package)
    findings = [
        f"高优先级资产池 {len(plan['high_priority_asset_pool'])} 个分层。",
        f"建议竞拍池 {len(plan['auction_pool'])} 个分层。",
        f"建议法务池 {len(plan['legal_pool'])} 个分层。",
        f"补资料池 {len(plan['data_completion_pool'])} 个来源。",
    ]
    if portfolio.capacity_plan:
        findings.append(f"本月可执行资产 {portfolio.capacity_plan.total_selected_assets} 台。")
    warnings = []
    if plan["capacity_bottlenecks"]:
        warnings.append(f"产能瓶颈：{'、'.join(plan['capacity_bottlenecks'][:4])}")
    if plan["paused_pool"]:
        warnings.append("存在暂缓处置池，需先解除物权、入库或路径可行性问题")
    if plan["data_completion_pool"]:
        warnings.append("存在资料缺口，直接推进竞拍或出让可能导致买方压价")

    return AgentOutput(
        summary="已生成本周半自动运营计划草稿，覆盖高优先级资产池、竞拍池、法务池、补资料池和暂缓处置池。",
        key_findings=findings,
        recommended_actions=[
            "经理复核高优先级资产池后确认本周推进范围",
            "主管按补资料池建立资料补齐任务",
            "竞拍和法务动作仅作为草稿进入人工确认",
        ],
        risk_warnings=warnings or ["暂未识别重大产能瓶颈，仍需人工复核排期和外部资源"],
        confidence_score=0.72 if portfolio.segments else 0.45,
        evidence=evidence
        + [
            _agent_status_evidence("operation_planning_agent"),
            AgentEvidence(
                source="portfolio_capacity_plan",
                label="operation_plan",
                value=plan,
                evidence_source="portfolio_capacity_plan",
                related_object_type="portfolio_snapshot",
                related_object_id=str(portfolio.snapshot_id) if portfolio.snapshot_id else None,
                calculation_basis="基于真实组合分层、资产包风险和产能约束生成规则化运营计划",
                data_quality_notes=portfolio.empty_reason,
            ),
        ],
        requires_human_review=True,
    )


def _deadline(days: int) -> str:
    return (datetime.utcnow() + timedelta(days=days)).date().isoformat()


def _task_draft(
    *,
    title: str,
    description: str,
    task_type: str,
    priority: str,
    related_object_type: str,
    related_object_id: Optional[str],
    suggested_owner_role: str,
    deadline_days: int,
    required_documents: list[str],
    expected_result: str,
) -> dict[str, Any]:
    return {
        "title": title,
        "description": description,
        "priority": priority,
        "task_type": task_type,
        "related_object_type": related_object_type,
        "related_object_id": related_object_id,
        "suggested_owner_role": suggested_owner_role,
        "deadline_suggestion": _deadline(deadline_days),
        "required_documents": required_documents,
        "expected_result": expected_result,
        "status": "draft",
        "requires_human_review": True,
    }


def _build_task_drafts(package: PackageContext, portfolio: PortfolioContext, request: AgentRunCreate) -> list[dict[str, Any]]:
    drafts: list[dict[str, Any]] = []
    if package.package is not None:
        counts = _asset_counts(package.assets)
        package_id = str(package.package.id)
        if counts["missing_valuation_count"] or counts["gps_offline_count"] or counts["ownership_pending_count"]:
            drafts.append(
                _task_draft(
                    title="补齐资产包关键资料",
                    description="针对估值缺失、GPS 离线、权属未完成等资产建立资料补齐清单。",
                    task_type="data_completion",
                    priority="high",
                    related_object_type="asset_package",
                    related_object_id=package_id,
                    suggested_owner_role="operator",
                    deadline_days=3,
                    required_documents=["车辆照片", "GPS 状态证明", "权属材料", "保险状态"],
                    expected_result="形成可复核的补资料清单并更新资产包风险状态",
                )
            )
        if counts["missing_valuation_count"]:
            drafts.append(
                _task_draft(
                    title="复核估值缺口车辆",
                    description=f"当前资产包存在 {counts['missing_valuation_count']} 台缺少估值车辆，需补充估值依据。",
                    task_type="valuation_review",
                    priority="high",
                    related_object_type="asset_package",
                    related_object_id=package_id,
                    suggested_owner_role="operator",
                    deadline_days=2,
                    required_documents=["车300估值记录", "人工复核备注"],
                    expected_result="补齐估值记录并标注估值置信度",
                )
            )
        if package.result is not None:
            drafts.append(
                _task_draft(
                    title="准备资产包竞拍材料",
                    description="基于定价结果整理竞拍底价、风险说明和资料包。",
                    task_type="auction_preparation",
                    priority="medium",
                    related_object_type="asset_package",
                    related_object_id=package_id,
                    suggested_owner_role="manager",
                    deadline_days=5,
                    required_documents=["定价结果", "风险提示", "竞拍底价审批记录"],
                    expected_result="形成待经理确认的竞拍准备清单",
                )
            )
            if package.result.summary.risk_alerts:
                drafts.append(
                    _task_draft(
                        title="复核法务材料完整性",
                        description="定价结果存在风险提示，需复核合同、权属和债权转让材料。",
                        task_type="legal_material_review",
                        priority="medium",
                        related_object_type="asset_package",
                        related_object_id=package_id,
                        suggested_owner_role="manager",
                        deadline_days=5,
                        required_documents=["贷款合同", "抵押登记", "债权余额表", "转让限制核查"],
                        expected_result="输出法务材料缺口和是否可推进出让的人工意见",
                    )
                )
    if request.buyer_offer_price is not None and package.package is not None:
        drafts.append(
            _task_draft(
                title="复核买方报价",
                description="买方报价仅作为谈判输入，需人工复核价格差异和让价空间。",
                task_type="buyer_offer_review",
                priority="high",
                related_object_type="asset_package",
                related_object_id=str(package.package.id),
                suggested_owner_role="manager",
                deadline_days=1,
                required_documents=["买方报价单", "系统建议价", "谈判记录"],
                expected_result="形成是否进入审批的买方报价复核意见",
            )
        )
    for item in (portfolio.capacity_plan.current_month_execution_plan if portfolio.capacity_plan else [])[:2]:
        if item.task_type == "collection":
            drafts.append(
                _task_draft(
                    title=f"跟进催收分层：{item.segment_name}",
                    description="对本月产能计划中的催收分层进行跟进。",
                    task_type="collection_follow_up",
                    priority="medium",
                    related_object_type="portfolio_segment",
                    related_object_id=item.segment_name,
                    suggested_owner_role="operator",
                    deadline_days=7,
                    required_documents=["催收记录", "还款承诺", "客户联系记录"],
                    expected_result="更新催收进展和下一步处置建议",
                )
            )
    drafts.append(
        _task_draft(
            title="复核 AI 指挥中心报告草稿",
            description="复核 Agent 生成的分析结论、证据和风险提示。",
            task_type="report_review",
            priority="low",
            related_object_type="agent_run",
            related_object_id=None,
            suggested_owner_role="manager",
            deadline_days=7,
            required_documents=["Agent 输出", "证据列表", "人工复核意见"],
            expected_result="确认报告草稿是否可进入正式审批或客户演示",
        )
    )
    return drafts[:8]


def _task_generation_agent(package: PackageContext, portfolio: PortfolioContext, request: AgentRunCreate) -> AgentOutput:
    evidence = _base_evidence(package)
    drafts = _build_task_drafts(package, portfolio, request)
    if not drafts:
        return AgentOutput(
            summary="暂无足够数据生成任务草稿。",
            key_findings=["未识别到可转化为任务草稿的数据缺口或运营动作"],
            recommended_actions=["先上传资产包、生成定价结果或导入真实组合数据"],
            risk_warnings=["不得在无依据时自动派发任务"],
            confidence_score=0.35,
            evidence=evidence + [_agent_status_evidence("task_generation_agent")],
            requires_human_review=True,
        )
    return AgentOutput(
        summary=f"已生成 {len(drafts)} 条待人工确认的任务草稿，不会自动派发。",
        key_findings=[
            f"{draft['task_type']}：{draft['title']}"
            for draft in drafts[:5]
        ],
        recommended_actions=[
            "经理复核任务草稿后再派发",
            "优先处理 high 优先级任务",
            "保留 required_documents 作为完成验收依据",
        ],
        risk_warnings=["任务仅为草稿，Agent 不会自动派发、确认完成或替代责任人判断"],
        confidence_score=0.7,
        evidence=evidence
        + [
            _agent_status_evidence("task_generation_agent"),
            AgentEvidence(
                source="agent_task_drafts",
                label="task_drafts",
                value=drafts,
                evidence_source="agent_task_drafts",
                related_object_type="agent_run",
                calculation_basis="根据资产包风险、定价结果、买方报价和产能计划生成任务草稿",
                data_quality_notes="草稿需人工确认后才能进入正式任务派发",
            ),
        ],
        requires_human_review=True,
    )


def _month_bounds() -> tuple[datetime, datetime]:
    start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        return start, start.replace(year=start.year + 1, month=1)
    return start, start.replace(month=start.month + 1)


def _resource_usage(session: Session, *, tenant_id: int, resource_type: str) -> float:
    start, end = _month_bounds()
    return sum(
        float(event.quantity or 0)
        for event in usage_repo.list_usage_events_for_period(
            session,
            tenant_id=tenant_id,
            start_at=start,
            end_at=end,
            resource_type=resource_type,
        )
    )


def _cost_control_agent(session: Session, tenant_id: int, package: PackageContext, request: AgentRunCreate) -> AgentOutput:
    evidence = _base_evidence(package)
    asset_count = len(package.assets) or int(package.package.total_assets if package.package else 0)
    vin_calls = int(request.expected_vin_calls if request.expected_vin_calls is not None else asset_count)
    condition_calls = int(
        request.expected_condition_pricing_calls
        if request.expected_condition_pricing_calls is not None
        else _asset_counts(package.assets)["missing_valuation_count"]
    )
    ai_reports = int(request.expected_ai_reports if request.expected_ai_reports is not None else 1)
    estimated_cost = round(
        vin_calls * settings.che300_basic_unit_cost
        + condition_calls * settings.che300_condition_pricing_unit_cost
        + ai_reports * settings.llm_plus_unit_cost,
        2,
    )
    subscription = subscription_repo.get_current_subscription(session, tenant_id=tenant_id)
    plan = plan_repo.get_plan_by_id(session, subscription.plan_id) if subscription else None
    quota = {
        "vin_call": {
            "limit": int(plan.included_vin_calls) if plan else 0,
            "used": _resource_usage(session, tenant_id=tenant_id, resource_type="vin_call"),
        },
        "condition_pricing": {
            "limit": int(plan.included_condition_pricing_points) if plan else 0,
            "used": _resource_usage(session, tenant_id=tenant_id, resource_type="condition_pricing"),
        },
        "ai_report": {
            "limit": int(plan.included_ai_reports) if plan else 0,
            "used": _resource_usage(session, tenant_id=tenant_id, resource_type="ai_report"),
        },
    }
    requested = {"vin_call": vin_calls, "condition_pricing": condition_calls, "ai_report": ai_reports}
    quota_remaining = {
        key: max(values["limit"] - values["used"] - requested[key], 0)
        for key, values in quota.items()
    }
    over_quota = [
        key
        for key, values in quota.items()
        if values["limit"] >= 0 and values["used"] + requested[key] > values["limit"]
    ]
    budget_limit = float(subscription.monthly_budget_limit or 0) if subscription else 0
    single_budget_exceeded = (
        request.single_task_budget is not None and estimated_cost > float(request.single_task_budget)
    )
    budget_warning = bool(over_quota or single_budget_exceeded or (budget_limit > 0 and estimated_cost > budget_limit * 0.8))
    approval_required = bool(budget_warning or condition_calls > 0)
    downgrade_suggestion = []
    if condition_calls > 0:
        downgrade_suggestion.append("高级车况估值可先降级为基础估值，异常车辆再补人工复核")
    if ai_reports > 1:
        downgrade_suggestion.append("AI 报告先合并为一份经理复核版，避免重复生成")
    if over_quota:
        downgrade_suggestion.append(f"超出额度项：{'、'.join(over_quota)}，需审批或调整批量范围")

    payload = {
        "estimated_cost": estimated_cost,
        "requested_usage": requested,
        "quota_remaining": quota_remaining,
        "budget_limit": budget_limit,
        "budget_warning": budget_warning,
        "approval_required": approval_required,
        "downgrade_suggestion": downgrade_suggestion or ["当前请求可按基础模式执行，正式调用前仍需人工确认"],
        "recommended_action": "提交管理员复核" if approval_required else "可进入人工确认后的低成本执行",
    }
    return AgentOutput(
        summary=f"本次预计内部成本约 {estimated_cost:,.2f} 元，{'需要审批' if approval_required else '未触发强审批'}。",
        key_findings=[
            f"预计 VIN 调用 {vin_calls} 次，高级车况 {condition_calls} 次，AI 报告 {ai_reports} 份。",
            f"额度剩余：VIN {quota_remaining['vin_call']}，高级车况 {quota_remaining['condition_pricing']}，AI 报告 {quota_remaining['ai_report']}。",
            f"审批要求：{'需要' if approval_required else '暂不需要'}。",
        ],
        recommended_actions=[payload["recommended_action"], *payload["downgrade_suggestion"]],
        risk_warnings=["成本控制 Agent 只做预估，不会自动批准高成本估值或消耗额度"],
        confidence_score=0.74 if plan else 0.45,
        evidence=evidence
        + [
            _agent_status_evidence("cost_control_agent"),
            AgentEvidence(
                source="quota_and_usage",
                label="cost_control",
                value=payload,
                evidence_source="usage_events",
                related_object_type="tenant",
                related_object_id=str(tenant_id),
                calculation_basis="按套餐额度、月度使用量和单次预算进行规则化成本预估",
                data_quality_notes="未执行真实扣费，仅作为审批前成本草案",
            ),
        ],
        requires_human_review=True,
    )


def _report_generation_agent(package: PackageContext, portfolio: PortfolioContext, request: AgentRunCreate) -> AgentOutput:
    evidence = _base_evidence(package)
    report_type = request.report_type or "executive_summary"
    supported = {
        "executive_summary": "高管摘要",
        "asset_package_brief": "资产包简报",
        "buyer_offer_memo": "买方报价备忘录",
        "weekly_operation_report": "周运营报告",
    }
    if report_type not in supported:
        report_type = "executive_summary"
    plan = _operation_plan_payload(portfolio, package)
    summary = package.result.summary if package.result else None
    draft = {
        "report_type": report_type,
        "title": supported[report_type],
        "sections": [
            {
                "heading": "核心判断",
                "content": (
                    f"资产包建议中位价约 {summary.recommended_transfer_price_mid:,.0f} 元，需人工复核。"
                    if summary
                    else "当前缺少完整定价结果，报告仅作为草稿。"
                ),
            },
            {
                "heading": "运营重点",
                "content": "；".join(plan["weekly_focus"]),
            },
            {
                "heading": "风险提示",
                "content": "Agent 不会自动下载、外发、审批或替代法律结论。",
            },
        ],
        "requires_human_review": True,
        "distribution": "draft_only",
    }
    return AgentOutput(
        summary=f"已生成《{supported[report_type]}》草稿，不会自动下载或对外发送。",
        key_findings=[section["heading"] for section in draft["sections"]],
        recommended_actions=["经理复核报告草稿", "补充人工意见和证据附件", "确认后再进入正式导出或客户沟通流程"],
        risk_warnings=["报告生成 Agent 只生成草稿，不自动下载、不自动发送、不替代法律结论"],
        confidence_score=0.68 if package.package or portfolio.segments else 0.4,
        evidence=evidence
        + [
            _agent_status_evidence("report_generation_agent"),
            AgentEvidence(
                source="report_draft",
                label="report_draft",
                value=draft,
                evidence_source="agent_orchestrator",
                related_object_type="report_draft",
                related_object_id=report_type,
                calculation_basis="基于资产包定价、运营计划和风险提示生成报告草稿",
                data_quality_notes="草稿未导出、未发送，需人工复核",
            ),
        ],
        requires_human_review=True,
    )


def _mock_agent(agent_type: str) -> AgentOutput:
    info = AGENT_CATALOG[agent_type]
    return AgentOutput(
        summary=f"{info['name']} 已预留接口；第一阶段返回安全草稿，不执行自动动作。",
        key_findings=["该 Agent 当前为第一阶段 mock 输出"],
        recommended_actions=["进入下一阶段后接入真实数据编排和审批流", "所有生成结果继续保持人工复核"],
        risk_warnings=["当前输出不能作为正式业务决策依据"],
        confidence_score=0.35,
        evidence=[
            AgentEvidence(
                source="agent_catalog",
                label="status",
                value=info["status"],
                evidence_source="agent_catalog",
                related_object_type="agent_type",
                related_object_id=agent_type,
                calculation_basis="第一阶段 Agent 目录状态",
                data_quality_notes="mock 表示预留接口，不代表已接入真实运营编排",
            )
        ],
        requires_human_review=True,
    )


def _run_agent_logic(session: Session, *, tenant_id: int, request: AgentRunCreate) -> AgentOutput:
    agent_type = request.agent_type or classify_intent(request.question)
    context = _latest_package_context(
        session,
        tenant_id=tenant_id,
        asset_package_id=request.asset_package_id,
    )
    if agent_type == "asset_package_diagnosis_agent":
        return _diagnose_asset_package(context)
    if agent_type == "valuation_analysis_agent":
        return _analyze_valuation(context)
    if agent_type == "pricing_strategy_agent":
        return _analyze_pricing(context)
    if agent_type == "buyer_offer_analysis_agent":
        return _analyze_buyer_offer(context, request)
    if agent_type == "operation_planning_agent":
        portfolio = _portfolio_context(session, tenant_id=tenant_id)
        return _operation_planning_agent(context, portfolio)
    if agent_type == "task_generation_agent":
        portfolio = _portfolio_context(session, tenant_id=tenant_id)
        return _task_generation_agent(context, portfolio, request)
    if agent_type == "report_generation_agent":
        portfolio = _portfolio_context(session, tenant_id=tenant_id)
        return _report_generation_agent(context, portfolio, request)
    if agent_type == "cost_control_agent":
        return _cost_control_agent(session, tenant_id, context, request)
    return _mock_agent(agent_type)


def _extract_task_drafts(output: AgentOutput) -> list[dict[str, Any]]:
    for item in output.evidence:
        if item.label == "task_drafts" and isinstance(item.value, list):
            return [row for row in item.value if isinstance(row, dict)]
    return []


def _apply_agent_status(output: AgentOutput, agent_type: str) -> AgentOutput:
    output.agent_status = AGENT_CATALOG.get(agent_type, {}).get("status", "fallback")
    return output


def run_agent(
    session: Session,
    *,
    tenant_id: int,
    user_id: int,
    request: AgentRunCreate,
) -> AgentRun:
    agent_type = request.agent_type or classify_intent(request.question)
    input_payload = request.model_dump(exclude_none=True)
    input_payload["resolved_agent_type"] = agent_type
    run = agent_repo.create_run(
        session,
        tenant_id=tenant_id,
        agent_type=agent_type,
        input_payload=input_payload,
        created_by=user_id,
        requires_human_review=True,
    )
    output = _apply_agent_status(
        _run_agent_logic(session, tenant_id=tenant_id, request=request),
        agent_type,
    )
    output.requires_human_review = True
    agent_repo.complete_run(
        run,
        output_payload=output.model_dump(),
        requires_human_review=True,
    )
    agent_repo.create_recommendation(
        session,
        tenant_id=tenant_id,
        agent_run_id=run.id,
        recommendation_type=agent_type,
        title=AGENT_CATALOG[agent_type]["name"],
        summary=output.summary,
        payload=output.model_dump(),
        confidence_score=output.confidence_score,
        requires_human_review=True,
        created_by=user_id,
    )
    if agent_type == "task_generation_agent":
        task_drafts = _extract_task_drafts(output)
        if not task_drafts:
            task_drafts = [
                {
                    "title": "AI 草拟任务：补充资料与人工复核",
                    "task_type": "data_completion",
                    "priority": "medium",
                    "status": "draft",
                    "requires_human_review": True,
                    "description": "任务生成 Agent 未识别到详细草稿，保留人工复核占位任务。",
                }
            ]
        for draft in task_drafts:
            title = str(draft.get("title") or "AI 草拟任务")
            task_type = str(draft.get("task_type") or "data_completion")
            priority = str(draft.get("priority") or "medium")
            payload = {
                **draft,
                "source": "task_generation_agent",
                "agent_run_id": run.id,
            }
            agent_repo.create_task(
                session,
                tenant_id=tenant_id,
                agent_run_id=run.id,
                title=title,
                task_type=task_type,
                priority=priority,
                payload=payload,
                created_by=user_id,
                requires_human_review=True,
            )
    agent_repo.create_decision_audit_log(
        session,
        tenant_id=tenant_id,
        agent_run_id=run.id,
        decision_type=agent_type,
        action="completed",
        actor_user_id=user_id,
        before=None,
        after={"agent_type": agent_type, "status": run.status},
        requires_human_review=True,
    )
    return run


def output_from_run(row: AgentRun) -> AgentOutput:
    payload = agent_repo.load_json(row.output_json)
    if not payload:
        payload = {
            "summary": "Agent 尚未生成输出。",
            "key_findings": [],
            "recommended_actions": [],
            "risk_warnings": ["Agent 执行未完成"],
            "confidence_score": 0,
            "evidence": [],
            "requires_human_review": True,
            "agent_status": "fallback",
        }
    return AgentOutput.model_validate(payload)


def has_agent_role(role: str, agent_type: Optional[str]) -> bool:
    if not agent_type:
        return role != "viewer"
    min_role = AGENT_CATALOG.get(agent_type, {}).get("min_role", "viewer")
    return role_rank(role) >= role_rank(min_role)


def redact_output_for_role(output: AgentOutput, role: str, agent_type: Optional[str] = None) -> AgentOutput:
    if role != "viewer" and has_agent_role(role, agent_type):
        return output
    return AgentOutput(
        summary=output.summary,
        key_findings=[],
        recommended_actions=[],
        risk_warnings=[],
        confidence_score=output.confidence_score,
        evidence=[],
        requires_human_review=output.requires_human_review,
        agent_status=output.agent_status,
    )


def serialize_run(row: AgentRun, *, role: str) -> AgentRunOut:
    return AgentRunOut(
        id=row.id,
        tenant_id=row.tenant_id,
        agent_type=row.agent_type,
        status=row.status,
        created_by=row.created_by,
        started_at=row.started_at.isoformat(),
        finished_at=row.finished_at.isoformat() if row.finished_at else None,
        requires_human_review=row.requires_human_review,
        input=agent_repo.load_json(row.input_json),
        output=redact_output_for_role(output_from_run(row), role, row.agent_type),
    )


def _serialize_task(row) -> AgentTaskOut:
    return AgentTaskOut(
        id=row.id,
        agent_run_id=row.agent_run_id,
        title=row.title,
        task_type=row.task_type,
        priority=row.priority,
        status=row.status,
        requires_human_review=row.requires_human_review,
        created_at=row.created_at.isoformat(),
        payload=agent_repo.load_json(row.payload_json),
    )


def _serialize_recommendation(row) -> AgentRecommendationOut:
    return AgentRecommendationOut(
        id=row.id,
        agent_run_id=row.agent_run_id,
        recommendation_type=row.recommendation_type,
        title=row.title,
        summary=row.summary,
        confidence_score=row.confidence_score,
        requires_human_review=row.requires_human_review,
        created_at=row.created_at.isoformat(),
    )


def build_overview(session: Session, *, tenant_id: int, role: str) -> AiCommandOverview:
    package_count = int(
        session.scalar(select(func.count(AssetPackage.id)).where(AssetPackage.tenant_id == tenant_id))
        or 0
    )
    pending_work_orders = int(
        session.scalar(
            select(func.count(WorkOrder.id))
            .where(WorkOrder.tenant_id == tenant_id)
            .where(WorkOrder.status.in_(["pending", "assigned", "in_progress", "blocked"]))
        )
        or 0
    )
    pending_approval_count = int(
        session.scalar(
            select(func.count(ApprovalRequest.id))
            .where(ApprovalRequest.tenant_id == tenant_id)
            .where(ApprovalRequest.status == "pending")
        )
        or 0
    )
    recent_runs = agent_repo.list_runs(session, tenant_id=tenant_id, limit=10)
    latest_run = recent_runs[0] if recent_runs else None
    latest_output = output_from_run(latest_run) if latest_run else AgentOutput(
        summary="AI 指挥中心已就绪，等待你发起资产包、估值、定价或买方报价分析。",
        key_findings=[],
        recommended_actions=["从 Agent 工作台选择一个分析方向", "输入自然语言问题后由系统路由到对应 Agent"],
        risk_warnings=["Agent 输出仅为建议草稿，关键动作必须人工复核"],
        confidence_score=0.5,
        evidence=[],
        requires_human_review=True,
        agent_status="fallback",
    )
    return AiCommandOverview(
        today_overview={
            "asset_package_count": package_count,
            "pending_work_orders": pending_work_orders,
            "pending_approval_count": pending_approval_count,
            "agent_runs_today": agent_repo.count_runs_today(session, tenant_id=tenant_id),
        },
        ai_today_judgment=redact_output_for_role(
            latest_output,
            role,
            latest_run.agent_type if latest_run else None,
        ),
        agent_workbench=[AgentWorkbenchItem(agent_type=key, **value) for key, value in AGENT_CATALOG.items()],
        pending_tasks=[
            _serialize_task(row)
            for row in (
                agent_repo.list_pending_tasks(session, tenant_id=tenant_id, limit=8)
                if role_rank(role) >= role_rank("manager")
                else []
            )
        ],
        pending_approvals=[
            _serialize_recommendation(row)
            for row in (
                agent_repo.list_recommendations(session, tenant_id=tenant_id, limit=8)
                if role_rank(role) >= role_rank("admin")
                else []
            )
        ],
        recent_runs=[serialize_run(row, role=role) for row in recent_runs],
        suggested_prompts=SUGGESTED_PROMPTS,
        role_scope=role,
    )
