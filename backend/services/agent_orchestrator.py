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
    AgentRuleSettings,
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


def _rule_profile_from_row(row) -> dict[str, Any]:
    if row is None:
        return {
            "agent_type": agent_repo.GLOBAL_RULE_AGENT_TYPE,
            "scenario": agent_repo.DEFAULT_RULE_SCENARIO,
            "version": 1,
            "is_active": True,
            "resolved_from": "system_default",
        }
    return {
        "agent_type": row.agent_type,
        "scenario": row.scenario,
        "version": row.version,
        "is_active": row.is_active,
        "resolved_from": "tenant_profile",
    }


def _rule_settings_evidence(
    rule_settings: AgentRuleSettings,
    rule_profile: dict[str, Any],
) -> AgentEvidence:
    thresholds = rule_settings.model_dump()
    return AgentEvidence(
        source="agent_rule_settings",
        label="rule_thresholds",
        value={
            **thresholds,
            "profile": rule_profile,
            "thresholds": thresholds,
        },
        evidence_source="agent_rule_settings",
        related_object_type="tenant_agent_rules",
        related_object_id=f"{rule_profile.get('agent_type')}:{rule_profile.get('scenario')}:v{rule_profile.get('version')}",
        calculation_basis="租户级 Agent/场景/版本化规则阈值配置",
        data_quality_notes="阈值只影响草稿生成和预警强度，不会自动执行业务动作",
    )


def _operation_plan_payload(
    portfolio: PortfolioContext,
    package: PackageContext,
    rule_settings: AgentRuleSettings,
    recent_recommendations: list[Any],
) -> dict[str, Any]:
    segments = portfolio.segments
    capacity = portfolio.capacity_plan
    pool_limit = rule_settings.operation_high_priority_limit
    high_priority = _top_segments(segments, "expected_loss_amount", limit=pool_limit)
    current_items = list(capacity.current_month_execution_plan if capacity else [])
    deferred_items = list(capacity.next_month_deferred_pool if capacity else [])
    paused_items = list(capacity.paused_pool if capacity else [])

    def capacity_pool(task_types: set[str], source_items: list[Any]) -> list[dict[str, Any]]:
        pool: list[dict[str, Any]] = []
        for item in source_items:
            if item.task_type not in task_types:
                continue
            payload = item.model_dump()
            payload["suggested_action"] = {
                "auction": "复核资料和底价后进入快速竞拍准备",
                "litigation": "复核合同、抵押和债权材料后推进法务路径",
                "special_procedure": "复核特殊程序适用条件后进入法务排期",
                "debt_transfer": "评估债权转让或外包清收可行性",
                "collection": "跟进还款意愿和现金流承诺",
                "restructure": "评估重组价值和暂缓处置窗口",
            }.get(item.task_type, "人工复核后再进入执行队列")
            pool.append(payload)
            if len(pool) >= pool_limit:
                break
        return pool

    auction_pool = capacity_pool({"auction"}, current_items)
    legal_pool = capacity_pool({"litigation", "special_procedure"}, current_items + deferred_items)
    debt_transfer_pool = capacity_pool({"debt_transfer"}, current_items + deferred_items)
    observe_pool = capacity_pool({"collection", "restructure"}, deferred_items)
    data_pool: list[dict[str, Any]] = []
    valuation_review_pool: list[dict[str, Any]] = []
    package_legal_pool: list[dict[str, Any]] = []
    package_debt_pool: list[dict[str, Any]] = []
    if package.package is not None:
        counts = _asset_counts(package.assets)
        data_gap_count = (
            counts["missing_valuation_count"]
            + counts["gps_offline_count"]
            + counts["ownership_pending_count"]
        )
        if data_gap_count >= rule_settings.operation_data_gap_min_count:
            data_pool.append(
                {
                    "package_id": package.package.id,
                    "package_name": package.package.name,
                    "missing_valuation_count": counts["missing_valuation_count"],
                    "gps_offline_count": counts["gps_offline_count"],
                    "ownership_pending_count": counts["ownership_pending_count"],
                }
            )
        if counts["missing_valuation_count"]:
            valuation_review_pool.append(
                {
                    "package_id": package.package.id,
                    "package_name": package.package.name,
                    "missing_valuation_count": counts["missing_valuation_count"],
                    "suggested_action": "补齐估值或发起估值复核后再进入报价/竞拍判断",
                }
            )
        if counts["ownership_pending_count"] or counts["insurance_lapsed_count"]:
            package_legal_pool.append(
                {
                    "package_id": package.package.id,
                    "package_name": package.package.name,
                    "ownership_pending_count": counts["ownership_pending_count"],
                    "insurance_lapsed_count": counts["insurance_lapsed_count"],
                    "suggested_action": "复核权属、合同、保险和债权转让限制",
                }
            )
        if counts["gps_offline_count"]:
            package_debt_pool.append(
                {
                    "package_id": package.package.id,
                    "package_name": package.package.name,
                    "gps_offline_count": counts["gps_offline_count"],
                    "suggested_action": "复核定位和收车难度，必要时进入债权转让或清收跟进池",
                }
            )
    recommendation_types = {row.recommendation_type for row in recent_recommendations}
    buyer_offer_review_pool = [
        {
            "agent_recommendation_id": row.id,
            "title": row.title,
            "summary": row.summary,
            "confidence_score": row.confidence_score,
            "suggested_action": "复核买方报价偏离、谈判空间和审批边界",
        }
        for row in recent_recommendations
        if row.recommendation_type == "buyer_offer_analysis_agent"
    ][:pool_limit]
    paused_pool = [item.model_dump() for item in paused_items[:pool_limit]]
    deferred_pool = [
        item.model_dump()
        for item in (capacity.next_month_deferred_pool if capacity else [])[:pool_limit]
    ]
    missing_data: list[str] = []
    if package.package is None:
        missing_data.append("asset_package")
    elif not package.assets:
        missing_data.append("asset_details")
    if package.package is not None and package.result is None:
        missing_data.append("pricing_result")
    if not segments:
        missing_data.append("portfolio_segments")
    if portfolio.empty_reason:
        missing_data.append("real_portfolio_capacity_plan")

    data_quality_notes: list[str] = []
    if portfolio.empty_reason:
        data_quality_notes.append(portfolio.empty_reason)
    if package.package is None:
        data_quality_notes.append("未找到资产包，资产包级分池仅能保持空状态")
    if package.package is not None and package.result is None:
        data_quality_notes.append("资产包尚无定价结果，竞拍/报价相关判断置信度受限")
    if "buyer_offer_analysis_agent" not in recommendation_types:
        data_quality_notes.append("未读取到最近买方报价分析 recommendation，报价复核池保持空状态")
    if capacity and capacity.budget_gap > 0:
        data_quality_notes.append("当前产能计划存在预算缺口，正式排期前需确认预算或额度")

    weekly_focus: list[str] = []
    if high_priority:
        weekly_focus.append("优先处理高损失贡献分层")
    if auction_pool:
        weekly_focus.append("推进已入库且路径可行的快速竞拍池")
    if legal_pool or package_legal_pool:
        weekly_focus.append("复核合同、权属和法务路径材料")
    if data_pool or valuation_review_pool:
        weekly_focus.append("补齐估值、GPS、权属等关键资料缺口")
    if debt_transfer_pool or package_debt_pool:
        weekly_focus.append("评估非在库或定位异常资产的债权转让/清收跟进路径")
    if not weekly_focus:
        weekly_focus.append("先补齐资产包、组合分层和定价结果，再形成正式作战计划")

    budget_constraints = {
        "capacity_bottlenecks": capacity.capacity_bottlenecks if capacity else [],
        "budget_gap": capacity.budget_gap if capacity else 0,
        "remaining_capacity": capacity.remaining_capacity if capacity else {},
        "resource_usage": capacity.resource_usage if capacity else {},
        "notes": [
            "所有产能和预算约束只用于排期建议，不会自动批准高成本估值或额度消耗",
            *([f"预算缺口约 {capacity.budget_gap:,.0f} 元" if capacity and capacity.budget_gap > 0 else "暂无明确预算缺口"]),
        ],
    }

    return {
        "title": "本周/月处置作战计划草稿",
        "agent_status": "rules_based",
        "requires_human_review": True,
        "weekly_focus": weekly_focus,
        "monthly_execution_plan": [item.model_dump() for item in current_items[:pool_limit]],
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
        "quick_auction_pool": auction_pool,
        "auction_pool": auction_pool,
        "legal_advancement_pool": legal_pool + package_legal_pool,
        "legal_pool": legal_pool,
        "valuation_review_pool": valuation_review_pool,
        "data_completion_pool": data_pool,
        "debt_transfer_pool": debt_transfer_pool + package_debt_pool,
        "observe_pool": observe_pool,
        "buyer_offer_review_pool": buyer_offer_review_pool,
        "paused_pool": paused_pool,
        "deferred_pool": deferred_pool,
        "risk_warnings": [
            warning
            for warning in [
                "存在资料缺口，直接推进竞拍或出让可能导致买方压价" if data_pool or valuation_review_pool else "",
                "存在法务或权属材料风险，需人工复核后才能推进路径" if legal_pool or package_legal_pool else "",
                "存在非在库/GPS 离线资产，需评估收车难度和债权转让可行性" if debt_transfer_pool or package_debt_pool else "",
                "存在产能或预算瓶颈，正式排期前需确认资源" if capacity and (capacity.capacity_bottlenecks or capacity.budget_gap > 0) else "",
            ]
            if warning
        ],
        "capacity_budget_constraints": budget_constraints,
        "capacity_bottlenecks": capacity.capacity_bottlenecks if capacity else [],
        "cashflow_focus": {
            "cash_30d": sum(float(segment.get("cash_30d") or 0) for segment in segments),
            "cash_90d": sum(float(segment.get("cash_90d") or 0) for segment in segments),
            "cash_180d": sum(float(segment.get("cash_180d") or 0) for segment in segments),
        },
        "missing_data": list(dict.fromkeys(missing_data)),
        "data_quality_notes": data_quality_notes,
        "limited_data_reason": "、".join(dict.fromkeys(missing_data)) if missing_data else None,
        "fallback_reason": "暂无真实组合数据和资产包数据" if portfolio.empty_reason and package.package is None else None,
        "next_agent_action": "如需落地执行，请基于本作战计划运行 task_generation_agent 生成 draft 任务草稿",
        "thresholds": rule_settings.model_dump(),
    }


def _operation_planning_agent(
    package: PackageContext,
    portfolio: PortfolioContext,
    rule_settings: AgentRuleSettings,
    rule_profile: dict[str, Any],
    recent_recommendations: list[Any],
) -> AgentOutput:
    evidence = _base_evidence(package)
    plan = _operation_plan_payload(portfolio, package, rule_settings, recent_recommendations)
    if portfolio.empty_reason and not portfolio.segments and package.package is None:
        return AgentOutput(
            summary="暂无真实组合数据和资产包数据，运营计划 Agent 已进入空数据安全模式。",
            key_findings=["未找到真实组合快照或资产包"],
            recommended_actions=["先导入组合数据或上传资产包，再生成本周作战计划"],
            risk_warnings=["无底层资产与产能数据时不得形成正式运营排期"],
            confidence_score=0.35,
            evidence=evidence
            + [
                _agent_status_evidence("operation_planning_agent"),
                _rule_settings_evidence(rule_settings, rule_profile),
                AgentEvidence(
                    source="portfolio_capacity_plan",
                    label="operation_plan",
                    value=plan,
                    evidence_source="portfolio_capacity_plan",
                    related_object_type="portfolio_snapshot",
                    related_object_id=str(portfolio.snapshot_id) if portfolio.snapshot_id else None,
                    calculation_basis="无真实数据时输出缺失项和下一步补录建议，不编造作战结论",
                    data_quality_notes=portfolio.empty_reason,
                ),
            ],
            requires_human_review=True,
        )

    findings = [
        f"高优先级资产池 {len(plan['high_priority_asset_pool'])} 个分层。",
        f"快速竞拍池 {len(plan['quick_auction_pool'])} 个分层。",
        f"法务推进池 {len(plan['legal_advancement_pool'])} 个来源。",
        f"补资料池 {len(plan['data_completion_pool'])} 个来源。",
        f"债权转让池 {len(plan['debt_transfer_pool'])} 个来源。",
        f"暂缓观察池 {len(plan['observe_pool']) + len(plan['paused_pool'])} 个来源。",
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
    warnings.extend([item for item in plan["risk_warnings"] if item not in warnings])
    if plan["missing_data"]:
        warnings.append(f"数据不完整：{'、'.join(plan['missing_data'])}")
    confidence = 0.78
    if plan["missing_data"]:
        confidence = 0.58 if portfolio.segments or package.package else 0.35
    elif not portfolio.segments:
        confidence = 0.45

    return AgentOutput(
        summary="已生成本周/月半自动处置作战计划草稿，覆盖高优先级资产池、快速竞拍池、法务推进池、补资料池、债权转让池和暂缓观察池。",
        key_findings=findings,
        recommended_actions=[
            "经理复核高优先级资产池后确认本周推进范围",
            "主管按补资料池建立资料补齐任务",
            "将快速竞拍、法务推进和债权转让动作转为 draft 任务草稿后再人工确认",
            "存在数据缺口时先补录缺失项，再复跑运营计划 Agent",
        ],
        risk_warnings=warnings or ["暂未识别重大产能瓶颈，仍需人工复核排期和外部资源"],
        confidence_score=confidence,
        evidence=evidence
        + [
            _agent_status_evidence("operation_planning_agent"),
            _rule_settings_evidence(rule_settings, rule_profile),
            AgentEvidence(
                source="agent_recommendations",
                label="recent_recommendation_types",
                value=[row.recommendation_type for row in recent_recommendations],
                evidence_source="agent_recommendations",
                related_object_type="agent_recommendation",
                calculation_basis="读取当前租户最近 Agent recommendation，辅助识别报价复核和任务转化线索",
                data_quality_notes="只读取当前租户 recommendation，不跨租户读取",
            ),
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
    evidence: list[dict[str, Any]],
    confidence_score: float,
) -> dict[str, Any]:
    return {
        "title": title,
        "description": description,
        "task_type": task_type,
        "priority": priority,
        "suggested_owner_role": suggested_owner_role,
        "deadline_suggestion": _deadline(deadline_days),
        "related_object_type": related_object_type,
        "related_object_id": related_object_id,
        "required_documents": required_documents,
        "expected_result": expected_result,
        "evidence": evidence,
        "confidence_score": round(max(0, min(confidence_score, 1)), 2),
        "status": "draft",
        "requires_human_review": True,
    }


def _build_task_drafts(
    package: PackageContext,
    portfolio: PortfolioContext,
    request: AgentRunCreate,
    rule_settings: AgentRuleSettings,
    recent_recommendations: list[Any],
) -> list[dict[str, Any]]:
    drafts: list[dict[str, Any]] = []
    urgent_days = rule_settings.task_urgent_deadline_days
    normal_days = rule_settings.task_normal_deadline_days
    recommendation_types = {row.recommendation_type for row in recent_recommendations}
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
                    deadline_days=urgent_days,
                    required_documents=["车辆照片", "GPS 状态证明", "权属材料", "保险状态"],
                    expected_result="形成可复核的补资料清单并更新资产包风险状态",
                    evidence=[
                        {"source": "assets", "label": "risk_counts", "value": counts},
                        {"source": "asset_packages", "label": "package_id", "value": package.package.id},
                    ],
                    confidence_score=_confidence_from_coverage(
                        counts["asset_count"],
                        counts["missing_valuation_count"],
                    ),
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
                    deadline_days=urgent_days,
                    required_documents=["车300估值记录", "人工复核备注"],
                    expected_result="补齐估值记录并标注估值置信度",
                    evidence=[
                        {
                            "source": "assets",
                            "label": "missing_valuation_count",
                            "value": counts["missing_valuation_count"],
                        }
                    ],
                    confidence_score=0.78,
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
                    deadline_days=normal_days,
                    required_documents=["定价结果", "风险提示", "竞拍底价审批记录"],
                    expected_result="形成待经理确认的竞拍准备清单",
                    evidence=[
                        {
                            "source": "asset_packages.results_json",
                            "label": "recommended_transfer_price_mid",
                            "value": package.result.summary.recommended_transfer_price_mid,
                        },
                        {
                            "source": "asset_packages.results_json",
                            "label": "tradeability_level",
                            "value": package.result.summary.tradeability_level,
                        },
                    ],
                    confidence_score=0.74,
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
                        deadline_days=normal_days,
                        required_documents=["贷款合同", "抵押登记", "债权余额表", "转让限制核查"],
                        expected_result="输出法务材料缺口和是否可推进出让的人工意见",
                        evidence=[
                            {
                                "source": "asset_packages.results_json",
                                "label": "risk_alerts",
                                "value": package.result.summary.risk_alerts,
                            }
                        ],
                        confidence_score=0.68,
                    )
                )
    if (
        (request.buyer_offer_price is not None or "buyer_offer_analysis_agent" in recommendation_types)
        and package.package is not None
    ):
        drafts.append(
            _task_draft(
                title="复核买方报价",
                description="买方报价仅作为谈判输入，需人工复核价格差异和让价空间。",
                task_type="buyer_offer_review",
                priority="high",
                related_object_type="asset_package",
                related_object_id=str(package.package.id),
                suggested_owner_role="manager",
                deadline_days=urgent_days,
                required_documents=["买方报价单", "系统建议价", "谈判记录"],
                expected_result="形成是否进入审批的买方报价复核意见",
                evidence=[
                    {"source": "buyer_offer", "label": "buyer_offer_price", "value": request.buyer_offer_price},
                    {
                        "source": "agent_recommendations",
                        "label": "has_prior_buyer_offer_recommendation",
                        "value": "buyer_offer_analysis_agent" in recommendation_types,
                    },
                ],
                confidence_score=0.72 if request.buyer_offer_price is not None else 0.58,
            )
        )
    if (
        (request.expected_condition_pricing_calls or 0) >= rule_settings.cost_condition_call_approval_threshold
        or request.single_task_budget is not None
        or "cost_control_agent" in recommendation_types
    ):
        drafts.append(
            _task_draft(
                title="复核高成本能力调用审批",
                description="本次任务可能涉及高级车况估值、AI 报告或单次预算，需要管理员复核额度与审批边界。",
                task_type="cost_approval",
                priority="high",
                related_object_type="tenant_cost_quota",
                related_object_id=None,
                suggested_owner_role="admin",
                deadline_days=urgent_days,
                required_documents=["成本预估", "套餐额度", "月度使用量", "审批说明"],
                expected_result="形成是否允许高成本能力调用的人工审批意见",
                evidence=[
                    {
                        "source": "agent_request",
                        "label": "expected_condition_pricing_calls",
                        "value": request.expected_condition_pricing_calls,
                    },
                    {
                        "source": "agent_request",
                        "label": "single_task_budget",
                        "value": request.single_task_budget,
                    },
                    {
                        "source": "agent_rule_settings",
                        "label": "cost_condition_call_approval_threshold",
                        "value": rule_settings.cost_condition_call_approval_threshold,
                    },
                ],
                confidence_score=0.66,
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
                    deadline_days=normal_days,
                    required_documents=["催收记录", "还款承诺", "客户联系记录"],
                    expected_result="更新催收进展和下一步处置建议",
                    evidence=[
                        {
                            "source": "portfolio_capacity_plan",
                            "label": "segment_name",
                            "value": item.segment_name,
                        },
                        {
                            "source": "portfolio_capacity_plan",
                            "label": "selected_count",
                            "value": item.selected_count,
                        },
                    ],
                    confidence_score=0.64,
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
            deadline_days=normal_days,
            required_documents=["Agent 输出", "证据列表", "人工复核意见"],
            expected_result="确认报告草稿是否可进入正式审批或客户演示",
            evidence=[
                {
                    "source": "agent_recommendations",
                    "label": "recent_recommendation_types",
                    "value": [row.recommendation_type for row in recent_recommendations],
                }
            ],
            confidence_score=0.55 if recent_recommendations else 0.45,
        )
    )
    return drafts[:rule_settings.task_max_drafts]


def _task_generation_agent(
    package: PackageContext,
    portfolio: PortfolioContext,
    request: AgentRunCreate,
    rule_settings: AgentRuleSettings,
    rule_profile: dict[str, Any],
    recent_recommendations: list[Any],
) -> AgentOutput:
    evidence = _base_evidence(package)
    drafts = _build_task_drafts(
        package,
        portfolio,
        request,
        rule_settings,
        recent_recommendations,
    )
    if not drafts:
        return AgentOutput(
            summary="暂无足够数据生成任务草稿。",
            key_findings=["未识别到可转化为任务草稿的数据缺口或运营动作"],
            recommended_actions=["先上传资产包、生成定价结果或导入真实组合数据"],
            risk_warnings=["不得在无依据时自动派发任务"],
            confidence_score=0.35,
            evidence=evidence
            + [
                _agent_status_evidence("task_generation_agent"),
                _rule_settings_evidence(rule_settings, rule_profile),
            ],
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
            _rule_settings_evidence(rule_settings, rule_profile),
            AgentEvidence(
                source="agent_task_drafts",
                label="task_drafts",
                value=drafts,
                evidence_source="agent_task_drafts",
                related_object_type="agent_run",
                calculation_basis="根据资产包风险、定价结果、买方报价和产能计划生成任务草稿",
                data_quality_notes="草稿需人工确认后才能进入正式任务派发",
            ),
            AgentEvidence(
                source="agent_recommendations",
                label="recent_recommendation_types",
                value=[row.recommendation_type for row in recent_recommendations],
                evidence_source="agent_recommendations",
                related_object_type="agent_recommendation",
                calculation_basis="读取当前租户最近 Agent recommendation，用于补充任务草稿上下文",
                data_quality_notes="只读取当前租户 recommendation，不跨租户读取",
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


def _cost_control_agent(
    session: Session,
    tenant_id: int,
    package: PackageContext,
    request: AgentRunCreate,
    rule_settings: AgentRuleSettings,
    rule_profile: dict[str, Any],
) -> AgentOutput:
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
    budget_threshold = budget_limit * rule_settings.cost_budget_warning_percent
    budget_warning = bool(
        over_quota
        or single_budget_exceeded
        or (budget_limit > 0 and estimated_cost > budget_threshold)
    )
    condition_approval_triggered = (
        condition_calls >= rule_settings.cost_condition_call_approval_threshold
    )
    approval_required = bool(budget_warning or condition_approval_triggered)
    downgrade_suggestion = []
    if condition_approval_triggered:
        downgrade_suggestion.append("高级车况估值可先降级为基础估值，异常车辆再补人工复核")
    if ai_reports >= rule_settings.cost_ai_report_merge_threshold:
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
        "thresholds": rule_settings.model_dump(),
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
            _rule_settings_evidence(rule_settings, rule_profile),
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


def _report_section(heading: str, content: str, evidence_refs: Optional[list[str]] = None) -> dict[str, Any]:
    return {
        "heading": heading,
        "content": content,
        "evidence_refs": evidence_refs or [],
    }


def _report_missing_data(
    package: PackageContext,
    portfolio: PortfolioContext,
    request: AgentRunCreate,
    report_type: str,
) -> list[str]:
    missing: list[str] = []
    if package.package is None:
        missing.append("asset_package")
    if package.result is None:
        missing.append("pricing_result")
    if not package.assets:
        missing.append("asset_details")
    if report_type == "buyer_offer_memo" and request.buyer_offer_price is None:
        missing.append("buyer_offer_price")
    if report_type == "weekly_operation_report" and not portfolio.segments:
        missing.append("portfolio_segments")
    return missing


def _report_data_quality_notes(
    missing_data: list[str],
    portfolio: PortfolioContext,
) -> list[str]:
    notes = ["报告草稿未导出、未发送，需人工复核后才能进入正式流程"]
    if missing_data:
        notes.append(f"缺失数据会降低报告置信度：{', '.join(missing_data)}")
    if portfolio.empty_reason:
        notes.append(portfolio.empty_reason)
    return notes


def _build_report_sections(
    package: PackageContext,
    portfolio: PortfolioContext,
    request: AgentRunCreate,
    report_type: str,
    rule_settings: AgentRuleSettings,
) -> list[dict[str, Any]]:
    package_name = package.package.name if package.package else "未选择资产包"
    counts = _asset_counts(package.assets)
    plan = _operation_plan_payload(portfolio, package, rule_settings, [])
    summary = package.result.summary if package.result else None
    price_text = (
        f"建议中位价约 {summary.recommended_transfer_price_mid:,.0f} 元，区间 "
        f"{summary.recommended_transfer_price_low:,.0f} - {summary.recommended_transfer_price_high:,.0f} 元。"
        if summary
        else "当前缺少完整定价结果，价格相关内容仅能作为待补充草稿。"
    )
    data_gap_text = (
        f"明细资产 {counts['asset_count']} 台，缺少估值 {counts['missing_valuation_count']} 台，"
        f"GPS 离线 {counts['gps_offline_count']} 台，权属未完成 {counts['ownership_pending_count']} 台。"
    )
    weekly_focus = "；".join(plan["weekly_focus"]) or "暂无可用作战重点，需先补充组合或资产包数据。"

    if report_type == "asset_package_brief":
        return [
            _report_section("资产包概况", f"{package_name} 当前可读取 {counts['asset_count']} 台资产明细。", ["package_id", "total_assets"]),
            _report_section("资料完整度", data_gap_text, ["risk_counts"]),
            _report_section("定价与估值摘要", price_text, ["recommended_transfer_price_mid"]),
            _report_section("建议补充材料", "优先补齐 VIN、里程、车况照片、权属和估值依据，避免买方压价。", ["missing_data"]),
        ]

    if report_type == "buyer_offer_memo":
        if package.result and request.buyer_offer_price is not None:
            analysis = analyze_buyer_offer(
                package.result,
                buyer_offer_price=request.buyer_offer_price,
                buyer_offer_note=request.buyer_offer_note,
            )
            offer_text = (
                f"买方报价 {analysis.buyer_offer_price:,.0f} 元，"
                f"相对系统中位建议差额 {analysis.buyer_offer_gap:,.0f} 元。"
            )
            action_text = "；".join(analysis.negotiation_suggestions[:3])
        else:
            offer_text = "当前缺少买方报价或定价结果，备忘录只能列出待补充项。"
            action_text = "补录买方报价、报价说明和内部建议价后再形成谈判意见。"
        return [
            _report_section("报价判断", offer_text, ["buyer_offer_price", "recommended_transfer_price_mid"]),
            _report_section("偏离说明", price_text, ["buyer_offer_gap_rate"]),
            _report_section("谈判建议", action_text, ["negotiation_suggestions"]),
            _report_section("复核边界", "Agent 不得自动接受报价，正式报价结论必须经理或审批人确认。", ["requires_human_review"]),
        ]

    if report_type == "weekly_operation_report":
        return [
            _report_section("本周作战重点", weekly_focus, ["operation_plan"]),
            _report_section(
                "分组资产池",
                (
                    f"高优先级 {len(plan['high_priority_asset_pool'])} 项，快速竞拍 {len(plan['quick_auction_pool'])} 项，"
                    f"法务推进 {len(plan['legal_advancement_pool'])} 项，补资料 {len(plan['data_completion_pool'])} 项。"
                ),
                ["operation_plan"],
            ),
            _report_section(
                "任务草稿与待确认",
                "如需落地执行，应由 task_generation_agent 生成 draft 任务草稿，并由 manager/admin 人工确认。",
                ["agent_tasks"],
            ),
            _report_section(
                "风险与资源约束",
                "；".join(plan["risk_warnings"][:3]) or "暂无明确风险阻断，仍需人工复核产能和预算。",
                ["capacity_budget_constraints"],
            ),
        ]

    return [
        _report_section("核心判断", f"{package_name} 已形成内部汇报草稿。{price_text}", ["package_id", "recommended_transfer_price_mid"]),
        _report_section("资产与风险概况", data_gap_text, ["risk_counts"]),
        _report_section("运营重点", weekly_focus, ["operation_plan"]),
        _report_section("人工复核事项", "正式导出、对外发送、法律判断和出让审批均需人工确认。", ["requires_human_review"]),
    ]


def _report_generation_agent(
    package: PackageContext,
    portfolio: PortfolioContext,
    request: AgentRunCreate,
    rule_settings: AgentRuleSettings,
    rule_profile: dict[str, Any],
) -> AgentOutput:
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
    missing_data = _report_missing_data(package, portfolio, request, report_type)
    data_quality_notes = _report_data_quality_notes(missing_data, portfolio)
    sections = _build_report_sections(
        package,
        portfolio,
        request,
        report_type,
        rule_settings,
    )[: rule_settings.report_max_sections]
    base_confidence = 0.68 if package.package or portfolio.segments else 0.4
    if package.result:
        base_confidence += 0.08
    if portfolio.segments:
        base_confidence += 0.05
    if missing_data:
        base_confidence -= min(0.25, 0.05 * len(missing_data))
    confidence = round(min(0.9, max(rule_settings.report_confidence_floor, base_confidence)), 2)
    draft = {
        "report_type": report_type,
        "title": supported[report_type],
        "status": "draft",
        "sections": sections,
        "review_checklist": [
            "核对底层资产、估值和定价证据",
            "补充人工判断和业务负责人意见",
            "确认是否进入正式审批、导出或客户沟通流程",
        ],
        "missing_data": missing_data,
        "data_quality_notes": data_quality_notes,
        "source_context": {
            "asset_package_id": package.package.id if package.package else None,
            "portfolio_snapshot_id": portfolio.snapshot_id,
            "portfolio_data_source": portfolio.capacity_plan.data_source if portfolio.capacity_plan else "unknown",
        },
        "confidence_score": confidence,
        "requires_human_review": True,
        "distribution": "draft_only",
        "allowed_actions": ["人工复核", "补充证据", "提交正式审批"],
        "forbidden_actions": ["自动下载", "自动外发", "自动批准出让", "替代法律结论"],
        "thresholds": rule_settings.model_dump(),
    }
    return AgentOutput(
        summary=f"已生成《{supported[report_type]}》草稿，不会自动下载或对外发送。",
        key_findings=[section["heading"] for section in draft["sections"]],
        recommended_actions=["经理复核报告草稿", "补充人工意见和证据附件", "确认后再进入正式导出或客户沟通流程"],
        risk_warnings=[
            "报告生成 Agent 只生成草稿，不自动下载、不自动发送、不替代法律结论",
            *([f"报告草稿缺失数据：{', '.join(missing_data)}"] if missing_data else []),
        ],
        confidence_score=confidence,
        evidence=evidence
        + [
            _agent_status_evidence("report_generation_agent"),
            _rule_settings_evidence(rule_settings, rule_profile),
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
    rule_row = agent_repo.resolve_rule_settings_row(
        session,
        tenant_id=tenant_id,
        agent_type=agent_type,
        scenario=request.rule_scenario,
    )
    rule_settings = agent_repo.to_rule_settings(rule_row) if rule_row else AgentRuleSettings()
    rule_profile = _rule_profile_from_row(rule_row)
    if agent_type == "operation_planning_agent":
        portfolio = _portfolio_context(session, tenant_id=tenant_id)
        recent_recommendations = agent_repo.list_recommendations(
            session,
            tenant_id=tenant_id,
            limit=5,
        )
        return _operation_planning_agent(
            context,
            portfolio,
            rule_settings,
            rule_profile,
            recent_recommendations,
        )
    if agent_type == "task_generation_agent":
        portfolio = _portfolio_context(session, tenant_id=tenant_id)
        recent_recommendations = agent_repo.list_recommendations(
            session,
            tenant_id=tenant_id,
            limit=5,
        )
        return _task_generation_agent(
            context,
            portfolio,
            request,
            rule_settings,
            rule_profile,
            recent_recommendations,
        )
    if agent_type == "report_generation_agent":
        portfolio = _portfolio_context(session, tenant_id=tenant_id)
        return _report_generation_agent(context, portfolio, request, rule_settings, rule_profile)
    if agent_type == "cost_control_agent":
        return _cost_control_agent(session, tenant_id, context, request, rule_settings, rule_profile)
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
                    "suggested_owner_role": "manager",
                    "deadline_suggestion": _deadline(7),
                    "related_object_type": "agent_run",
                    "related_object_id": str(run.id),
                    "required_documents": ["Agent 输出", "人工复核意见"],
                    "expected_result": "确认是否需要补充正式任务草稿",
                    "evidence": [{"source": "agent_run", "label": "agent_run_id", "value": run.id}],
                    "confidence_score": 0.35,
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
                if role_rank(role) >= role_rank("operator")
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
