"""First-stage AI command center orchestration.

The orchestrator owns Agent routing, data collection, fallback output and
persistence. Frontend callers never talk to an LLM directly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
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
from repositories import agent_repo, asset_package_repo
from services.buyer_offer_analysis import analyze_buyer_offer


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
        "stage": "reserved",
        "status": "mock",
        "min_role": "manager",
    },
    "task_generation_agent": {
        "name": "任务生成 Agent",
        "stage": "reserved",
        "status": "mock",
        "min_role": "manager",
    },
    "report_generation_agent": {
        "name": "报告生成 Agent",
        "stage": "reserved",
        "status": "mock",
        "min_role": "manager",
    },
    "cost_control_agent": {
        "name": "成本控制 Agent",
        "stage": "reserved",
        "status": "mock",
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
    return _mock_agent(agent_type)


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
    output = _run_agent_logic(session, tenant_id=tenant_id, request=request)
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
        agent_repo.create_task(
            session,
            tenant_id=tenant_id,
            agent_run_id=run.id,
            title="AI 草拟任务：补充资料与人工复核",
            task_type="human_review",
            priority="medium",
            payload={"source": "task_generation_agent", "recommended_actions": output.recommended_actions},
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
