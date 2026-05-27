"""AI command center APIs backed by Agent Orchestrator."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.models.user import User
from db.models.role import role_rank
from db.session import get_db_session
from dependencies.auth import get_current_user, require_role
from errors import BusinessError, Forbidden
from models.ai_command import (
    AgentReviewInsightOut,
    AgentRuleProfileSummary,
    AgentRuleSettings,
    AgentRuleSettingsOut,
    AgentRuleSettingsUpsert,
    AgentRunReviewCreate,
    AgentRunReviewOut,
    AgentRunCreate,
    AgentRunOut,
    AgentTaskDecisionCreate,
    AgentTaskOut,
    AiCommandOverview,
    DecisionAuditLogOut,
)
from repositories import agent_repo, work_order_repo
from services.agent_orchestrator import (
    AGENT_CATALOG,
    build_overview,
    classify_intent,
    run_agent,
    serialize_run,
)
from services.tenant_context import get_current_tenant_id


router = APIRouter(
    prefix="/api/ai-command-center",
    tags=["AI 指挥中心"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/overview", response_model=AiCommandOverview)
def overview(
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return build_overview(session, tenant_id=tenant_id, role=user.role)


@router.post("/runs", response_model=AgentRunOut, dependencies=[Depends(require_role("operator"))])
def create_agent_run(
    req: AgentRunCreate,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    agent_type = req.agent_type or classify_intent(req.question)
    if agent_type not in AGENT_CATALOG:
        raise BusinessError(
            "unsupported_agent_type",
            "不支持的 Agent 类型",
            400,
            {"supported_agent_types": list(AGENT_CATALOG.keys())},
        )
    min_role = AGENT_CATALOG.get(agent_type, {}).get("min_role", "operator")
    if role_rank(user.role) < role_rank(min_role):
        raise Forbidden(f"当前角色无权运行 {AGENT_CATALOG[agent_type]['name']}")
    row = run_agent(session, tenant_id=tenant_id, user_id=user.id, request=req)
    return serialize_run(row, role=user.role)


@router.get("/runs", response_model=list[AgentRunOut])
def list_agent_runs(
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return [
        serialize_run(row, role=user.role)
        for row in agent_repo.list_runs(session, tenant_id=tenant_id, limit=limit)
    ]


@router.get("/runs/{run_id:int}", response_model=AgentRunOut)
def get_agent_run(
    run_id: int,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    row = agent_repo.get_run(session, run_id, tenant_id=tenant_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Agent 执行记录不存在")
    return serialize_run(row, role=user.role)


def _rule_settings_out(row, tenant_id: int) -> AgentRuleSettingsOut:
    settings = agent_repo.to_rule_settings(row) if row else AgentRuleSettings()
    return AgentRuleSettingsOut(
        **settings.model_dump(),
        tenant_id=tenant_id,
        agent_type=row.agent_type if row else agent_repo.GLOBAL_RULE_AGENT_TYPE,
        scenario=row.scenario if row else agent_repo.DEFAULT_RULE_SCENARIO,
        version=row.version if row else 1,
        is_active=row.is_active if row else True,
        updated_by=row.updated_by if row else None,
        updated_at=row.updated_at.isoformat() if row else None,
    )


def _rule_profile_summary(row) -> AgentRuleProfileSummary:
    return AgentRuleProfileSummary(
        tenant_id=row.tenant_id,
        agent_type=row.agent_type,
        scenario=row.scenario,
        version=row.version,
        is_active=row.is_active,
        updated_by=row.updated_by,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


def _review_out(row) -> AgentRunReviewOut:
    return AgentRunReviewOut(
        id=row.id,
        tenant_id=row.tenant_id,
        agent_run_id=row.agent_run_id,
        reviewer_user_id=row.reviewer_user_id,
        outcome=row.outcome,
        usefulness_score=row.usefulness_score,
        accuracy_score=row.accuracy_score,
        accepted_actions_count=row.accepted_actions_count,
        rejected_actions_count=row.rejected_actions_count,
        follow_up_required=row.follow_up_required,
        feedback=row.feedback,
        created_at=row.created_at.isoformat(),
    )


def _agent_task_out(row) -> AgentTaskOut:
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


def _get_agent_task_or_404(session: Session, task_id: int, tenant_id: int):
    row = agent_repo.get_task(session, task_id, tenant_id=tenant_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Agent 任务草稿不存在")
    return row


def _priority_for_work_order(priority: str) -> str:
    return priority if priority in {"high", "medium", "low", "normal"} else "medium"


def _review_insights(rows, tenant_id: int) -> AgentReviewInsightOut:
    review_count = len(rows)
    if review_count == 0:
        return AgentReviewInsightOut(
            tenant_id=tenant_id,
            review_count=0,
            average_usefulness_score=0,
            average_accuracy_score=0,
            accepted_actions_count=0,
            rejected_actions_count=0,
            follow_up_required_count=0,
            acceptance_rate=0,
            recommendations=["暂无复盘样本，先完成至少 3 次人工复核后再调整规则阈值"],
            requires_human_review=True,
        )

    accepted_actions = sum(row.accepted_actions_count for row in rows)
    rejected_actions = sum(row.rejected_actions_count for row in rows)
    total_actions = accepted_actions + rejected_actions
    follow_up_count = sum(1 for row in rows if row.follow_up_required)
    avg_usefulness = round(sum(row.usefulness_score for row in rows) / review_count, 2)
    avg_accuracy = round(sum(row.accuracy_score for row in rows) / review_count, 2)
    acceptance_rate = round(accepted_actions / total_actions, 4) if total_actions else 0
    recommendations: list[str] = []
    if avg_accuracy < 3.5:
        recommendations.append("准确性评分偏低，建议复核 Agent evidence 和阈值配置")
    if avg_usefulness < 3.5:
        recommendations.append("有用性评分偏低，建议收窄任务草稿数量或优化运营计划池")
    if rejected_actions > accepted_actions:
        recommendations.append("驳回动作多于采纳动作，建议降低输出强度并增加人工解释")
    if follow_up_count:
        recommendations.append("存在需跟进复盘项，建议在下轮规则配置前完成原因归因")
    if not recommendations:
        recommendations.append("复盘结果稳定，可保持当前规则阈值并继续积累样本")
    return AgentReviewInsightOut(
        tenant_id=tenant_id,
        review_count=review_count,
        average_usefulness_score=avg_usefulness,
        average_accuracy_score=avg_accuracy,
        accepted_actions_count=accepted_actions,
        rejected_actions_count=rejected_actions,
        follow_up_required_count=follow_up_count,
        acceptance_rate=acceptance_rate,
        recommendations=recommendations,
        requires_human_review=True,
    )


@router.post(
    "/tasks/{task_id:int}/confirm",
    response_model=AgentTaskOut,
    dependencies=[Depends(require_role("manager"))],
)
def confirm_agent_task_draft(
    task_id: int,
    req: Optional[AgentTaskDecisionCreate] = None,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    row = _get_agent_task_or_404(session, task_id, tenant_id)
    if row.status != "draft":
        raise BusinessError("agent_task_already_decided", "任务草稿已处理，不能重复确认", 409)
    if row.priority == "high" and role_rank(user.role) < role_rank("admin"):
        raise Forbidden("高风险任务草稿需 admin 确认")

    before = _agent_task_out(row).model_dump()
    payload = agent_repo.load_json(row.payload_json)
    decided_at = datetime.utcnow().isoformat()
    work_order = work_order_repo.create_work_order(
        session,
        tenant_id=tenant_id,
        created_by=user.id,
        order_type=row.task_type,
        status="pending",
        priority=_priority_for_work_order(row.priority),
        title=row.title,
        target_description=str(payload.get("description") or ""),
        source_type="agent_task",
        source_id=str(row.id),
        payload={
            "agent_task_id": row.id,
            "agent_run_id": row.agent_run_id,
            "source": "task_generation_agent",
            "related_object_type": payload.get("related_object_type"),
            "related_object_id": payload.get("related_object_id"),
            "suggested_owner_role": payload.get("suggested_owner_role"),
            "deadline": payload.get("deadline_suggestion"),
            "required_documents": payload.get("required_documents") or [],
            "expected_result": payload.get("expected_result"),
            "confirmation_reason": req.reason if req else None,
            "requires_human_review": True,
        },
    )
    next_payload = {
        **payload,
        "status": "confirmed",
        "confirmed_by": user.id,
        "confirmed_at": decided_at,
        "confirmation_reason": req.reason if req else None,
        "work_order_id": work_order.id,
        "work_order_status": work_order.status,
    }
    agent_repo.update_task(row, status="confirmed", payload=next_payload)
    after = _agent_task_out(row).model_dump()
    agent_repo.create_decision_audit_log(
        session,
        tenant_id=tenant_id,
        agent_run_id=row.agent_run_id,
        decision_type="agent_task_confirmation",
        action="confirmed",
        actor_user_id=user.id,
        before=before,
        after={
            **after,
            "work_order_id": work_order.id,
            "work_order_status": work_order.status,
            "requires_human_review": True,
        },
        requires_human_review=True,
    )
    return _agent_task_out(row)


@router.post(
    "/tasks/{task_id:int}/reject",
    response_model=AgentTaskOut,
    dependencies=[Depends(require_role("manager"))],
)
def reject_agent_task_draft(
    task_id: int,
    req: Optional[AgentTaskDecisionCreate] = None,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    row = _get_agent_task_or_404(session, task_id, tenant_id)
    if row.status != "draft":
        raise BusinessError("agent_task_already_decided", "任务草稿已处理，不能重复驳回", 409)

    before = _agent_task_out(row).model_dump()
    payload = agent_repo.load_json(row.payload_json)
    next_payload = {
        **payload,
        "status": "rejected",
        "rejected_by": user.id,
        "rejected_at": datetime.utcnow().isoformat(),
        "rejection_reason": req.reason if req else None,
    }
    agent_repo.update_task(row, status="rejected", payload=next_payload)
    after = _agent_task_out(row).model_dump()
    agent_repo.create_decision_audit_log(
        session,
        tenant_id=tenant_id,
        agent_run_id=row.agent_run_id,
        decision_type="agent_task_confirmation",
        action="rejected",
        actor_user_id=user.id,
        before=before,
        after={**after, "requires_human_review": True},
        requires_human_review=True,
    )
    return _agent_task_out(row)


@router.get(
    "/settings",
    response_model=AgentRuleSettingsOut,
    dependencies=[Depends(require_role("manager"))],
)
def read_agent_rule_settings(
    agent_type: str = Query(default=agent_repo.GLOBAL_RULE_AGENT_TYPE, max_length=64),
    scenario: str = Query(default=agent_repo.DEFAULT_RULE_SCENARIO, max_length=64),
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    row = agent_repo.resolve_rule_settings_row(
        session,
        tenant_id=tenant_id,
        agent_type=agent_type,
        scenario=scenario,
    )
    return _rule_settings_out(row, tenant_id)


@router.get(
    "/settings/profiles",
    response_model=list[AgentRuleProfileSummary],
    dependencies=[Depends(require_role("manager"))],
)
def list_agent_rule_profiles(
    limit: int = Query(default=100, ge=1, le=200),
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return [
        _rule_profile_summary(row)
        for row in agent_repo.list_rule_setting_profiles(
            session,
            tenant_id=tenant_id,
            limit=limit,
        )
    ]


@router.put(
    "/settings",
    response_model=AgentRuleSettingsOut,
    dependencies=[Depends(require_role("admin"))],
)
def update_agent_rule_settings(
    req: AgentRuleSettingsUpsert,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    before_row = agent_repo.resolve_rule_settings_row(
        session,
        tenant_id=tenant_id,
        agent_type=req.agent_type,
        scenario=req.scenario,
    )
    before_settings = agent_repo.to_rule_settings(before_row) if before_row else AgentRuleSettings()
    before = {
        **before_settings.model_dump(),
        "agent_type": before_row.agent_type if before_row else req.agent_type,
        "scenario": before_row.scenario if before_row else req.scenario,
        "version": before_row.version if before_row else None,
        "is_active": before_row.is_active if before_row else None,
    }
    settings = AgentRuleSettings.model_validate(req.model_dump())
    row = agent_repo.upsert_rule_settings(
        session,
        tenant_id=tenant_id,
        settings=settings,
        updated_by=user.id,
        agent_type=req.agent_type,
        scenario=req.scenario,
        is_active=req.is_active,
    )
    after = {
        **agent_repo.to_rule_settings(row).model_dump(),
        "agent_type": row.agent_type,
        "scenario": row.scenario,
        "version": row.version,
        "is_active": row.is_active,
    }
    agent_repo.create_decision_audit_log(
        session,
        tenant_id=tenant_id,
        agent_run_id=None,
        decision_type="agent_rule_settings",
        action="updated",
        actor_user_id=user.id,
        before=before,
        after=after,
        requires_human_review=True,
    )
    return _rule_settings_out(row, tenant_id)


@router.get(
    "/run-reviews",
    response_model=list[AgentRunReviewOut],
    dependencies=[Depends(require_role("manager"))],
)
def list_agent_run_reviews(
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return [
        _review_out(row)
        for row in agent_repo.list_run_reviews(session, tenant_id=tenant_id, limit=limit)
    ]


@router.get(
    "/run-reviews/insights",
    response_model=AgentReviewInsightOut,
    dependencies=[Depends(require_role("manager"))],
)
def get_agent_run_review_insights(
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    rows = agent_repo.list_run_reviews(session, tenant_id=tenant_id, limit=limit)
    return _review_insights(rows, tenant_id)


@router.get(
    "/runs/{run_id:int}/reviews",
    response_model=list[AgentRunReviewOut],
    dependencies=[Depends(require_role("manager"))],
)
def list_reviews_for_run(
    run_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    row = agent_repo.get_run(session, run_id, tenant_id=tenant_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Agent 执行记录不存在")
    return [
        _review_out(review)
        for review in agent_repo.list_run_reviews(
            session,
            tenant_id=tenant_id,
            agent_run_id=run_id,
            limit=limit,
        )
    ]


@router.post(
    "/runs/{run_id:int}/reviews",
    response_model=AgentRunReviewOut,
    dependencies=[Depends(require_role("manager"))],
)
def create_review_for_run(
    run_id: int,
    req: AgentRunReviewCreate,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    row = agent_repo.get_run(session, run_id, tenant_id=tenant_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Agent 执行记录不存在")
    review = agent_repo.create_run_review(
        session,
        tenant_id=tenant_id,
        agent_run_id=row.id,
        reviewer_user_id=user.id,
        review=req,
    )
    agent_repo.create_decision_audit_log(
        session,
        tenant_id=tenant_id,
        agent_run_id=row.id,
        decision_type="agent_run_review",
        action="created",
        actor_user_id=user.id,
        before={"agent_run_status": row.status},
        after=req.model_dump(),
        requires_human_review=True,
    )
    return _review_out(review)


@router.get(
    "/decision-audit-logs",
    response_model=list[DecisionAuditLogOut],
    dependencies=[Depends(require_role("admin"))],
)
def list_decision_audit_logs(
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    rows = agent_repo.list_decision_audit_logs(session, tenant_id=tenant_id, limit=limit)
    return [
        DecisionAuditLogOut(
            id=row.id,
            tenant_id=row.tenant_id,
            agent_run_id=row.agent_run_id,
            decision_type=row.decision_type,
            action=row.action,
            actor_user_id=row.actor_user_id,
            requires_human_review=row.requires_human_review,
            created_at=row.created_at.isoformat(),
            after=agent_repo.load_json(row.after_json),
        )
        for row in rows
    ]
