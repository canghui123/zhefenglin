"""Repository helpers for AI command center agent records."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models.agent import (
    AgentRecommendation,
    AgentRuleSetting,
    AgentRun,
    AgentRunReview,
    AgentTask,
    DecisionAuditLog,
)
from models.ai_command import AgentRuleSettings, AgentRunReviewCreate


GLOBAL_RULE_AGENT_TYPE = "global"
DEFAULT_RULE_SCENARIO = "default"


def dump_json(value: Optional[dict[str, Any]]) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def load_json(value: Optional[str]) -> dict[str, Any]:
    if not value:
        return {}
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def create_run(
    session: Session,
    *,
    tenant_id: int,
    agent_type: str,
    input_payload: dict[str, Any],
    created_by: Optional[int],
    requires_human_review: bool = True,
) -> AgentRun:
    row = AgentRun(
        tenant_id=tenant_id,
        agent_type=agent_type,
        input_json=dump_json(input_payload) or "{}",
        status="running",
        created_by=created_by,
        started_at=datetime.utcnow(),
        requires_human_review=requires_human_review,
    )
    session.add(row)
    session.flush()
    return row


def complete_run(
    row: AgentRun,
    *,
    output_payload: dict[str, Any],
    status: str = "succeeded",
    requires_human_review: bool = True,
) -> AgentRun:
    row.output_json = dump_json(output_payload)
    row.status = status
    row.finished_at = datetime.utcnow()
    row.requires_human_review = requires_human_review
    return row


def get_run(session: Session, run_id: int, *, tenant_id: int) -> Optional[AgentRun]:
    stmt = (
        select(AgentRun)
        .where(AgentRun.id == run_id)
        .where(AgentRun.tenant_id == tenant_id)
        .limit(1)
    )
    return session.scalars(stmt).first()


def list_runs(
    session: Session,
    *,
    tenant_id: int,
    limit: int = 20,
) -> list[AgentRun]:
    stmt = (
        select(AgentRun)
        .where(AgentRun.tenant_id == tenant_id)
        .order_by(AgentRun.started_at.desc(), AgentRun.id.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def count_runs_today(session: Session, *, tenant_id: int) -> int:
    stmt = (
        select(func.count(AgentRun.id))
        .where(AgentRun.tenant_id == tenant_id)
        .where(func.date(AgentRun.started_at) == func.current_date())
    )
    return int(session.scalar(stmt) or 0)


def create_recommendation(
    session: Session,
    *,
    tenant_id: int,
    agent_run_id: int,
    recommendation_type: str,
    title: str,
    summary: str,
    payload: dict[str, Any],
    confidence_score: float,
    requires_human_review: bool,
    created_by: Optional[int],
) -> AgentRecommendation:
    row = AgentRecommendation(
        tenant_id=tenant_id,
        agent_run_id=agent_run_id,
        recommendation_type=recommendation_type,
        title=title,
        summary=summary,
        payload_json=dump_json(payload),
        confidence_score=confidence_score,
        requires_human_review=requires_human_review,
        created_by=created_by,
    )
    session.add(row)
    session.flush()
    return row


def list_recommendations(
    session: Session,
    *,
    tenant_id: int,
    limit: int = 20,
) -> list[AgentRecommendation]:
    stmt = (
        select(AgentRecommendation)
        .where(AgentRecommendation.tenant_id == tenant_id)
        .order_by(AgentRecommendation.created_at.desc(), AgentRecommendation.id.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def create_task(
    session: Session,
    *,
    tenant_id: int,
    agent_run_id: int,
    title: str,
    task_type: str,
    priority: str,
    payload: dict[str, Any],
    created_by: Optional[int],
    requires_human_review: bool = True,
) -> AgentTask:
    row = AgentTask(
        tenant_id=tenant_id,
        agent_run_id=agent_run_id,
        title=title,
        task_type=task_type,
        priority=priority,
        status="draft",
        payload_json=dump_json(payload),
        created_by=created_by,
        requires_human_review=requires_human_review,
    )
    session.add(row)
    session.flush()
    return row


def get_task(session: Session, task_id: int, *, tenant_id: int) -> Optional[AgentTask]:
    stmt = (
        select(AgentTask)
        .where(AgentTask.id == task_id)
        .where(AgentTask.tenant_id == tenant_id)
        .limit(1)
    )
    return session.scalars(stmt).first()


def update_task(
    row: AgentTask,
    *,
    status: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> AgentTask:
    if status is not None:
        row.status = status
    if payload is not None:
        row.payload_json = dump_json(payload)
    return row


def list_pending_tasks(
    session: Session,
    *,
    tenant_id: int,
    limit: int = 20,
) -> list[AgentTask]:
    stmt = (
        select(AgentTask)
        .where(AgentTask.tenant_id == tenant_id)
        .where(AgentTask.status == "draft")
        .order_by(AgentTask.created_at.desc(), AgentTask.id.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def create_decision_audit_log(
    session: Session,
    *,
    tenant_id: int,
    agent_run_id: Optional[int],
    decision_type: str,
    action: str,
    actor_user_id: Optional[int],
    before: Optional[dict[str, Any]],
    after: Optional[dict[str, Any]],
    requires_human_review: bool,
) -> DecisionAuditLog:
    row = DecisionAuditLog(
        tenant_id=tenant_id,
        agent_run_id=agent_run_id,
        decision_type=decision_type,
        action=action,
        actor_user_id=actor_user_id,
        before_json=dump_json(before),
        after_json=dump_json(after),
        requires_human_review=requires_human_review,
    )
    session.add(row)
    session.flush()
    return row


def list_decision_audit_logs(
    session: Session,
    *,
    tenant_id: int,
    limit: int = 20,
) -> list[DecisionAuditLog]:
    stmt = (
        select(DecisionAuditLog)
        .where(DecisionAuditLog.tenant_id == tenant_id)
        .order_by(DecisionAuditLog.created_at.desc(), DecisionAuditLog.id.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


RULE_SETTING_FIELDS = (
    "operation_high_priority_limit",
    "operation_data_gap_min_count",
    "task_max_drafts",
    "task_urgent_deadline_days",
    "task_normal_deadline_days",
    "cost_budget_warning_percent",
    "cost_condition_call_approval_threshold",
    "cost_ai_report_merge_threshold",
    "report_confidence_floor",
    "report_max_sections",
)


def get_rule_settings_row(
    session: Session,
    *,
    tenant_id: int,
    agent_type: str = GLOBAL_RULE_AGENT_TYPE,
    scenario: str = DEFAULT_RULE_SCENARIO,
) -> Optional[AgentRuleSetting]:
    stmt = (
        select(AgentRuleSetting)
        .where(AgentRuleSetting.tenant_id == tenant_id)
        .where(AgentRuleSetting.agent_type == agent_type)
        .where(AgentRuleSetting.scenario == scenario)
        .where(AgentRuleSetting.is_active.is_(True))
        .order_by(AgentRuleSetting.version.desc(), AgentRuleSetting.id.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def to_rule_settings(row: AgentRuleSetting) -> AgentRuleSettings:
    return AgentRuleSettings(**{field: getattr(row, field) for field in RULE_SETTING_FIELDS})


def resolve_rule_settings_row(
    session: Session,
    *,
    tenant_id: int,
    agent_type: Optional[str] = None,
    scenario: Optional[str] = None,
) -> Optional[AgentRuleSetting]:
    normalized_agent_type = (agent_type or GLOBAL_RULE_AGENT_TYPE).strip() or GLOBAL_RULE_AGENT_TYPE
    normalized_scenario = (scenario or DEFAULT_RULE_SCENARIO).strip() or DEFAULT_RULE_SCENARIO
    candidates = (
        (normalized_agent_type, normalized_scenario),
        (normalized_agent_type, DEFAULT_RULE_SCENARIO),
        (GLOBAL_RULE_AGENT_TYPE, normalized_scenario),
        (GLOBAL_RULE_AGENT_TYPE, DEFAULT_RULE_SCENARIO),
    )
    seen: set[tuple[str, str]] = set()
    for candidate_agent_type, candidate_scenario in candidates:
        key = (candidate_agent_type, candidate_scenario)
        if key in seen:
            continue
        seen.add(key)
        row = get_rule_settings_row(
            session,
            tenant_id=tenant_id,
            agent_type=candidate_agent_type,
            scenario=candidate_scenario,
        )
        if row is not None:
            return row
    return None


def get_rule_settings(
    session: Session,
    *,
    tenant_id: int,
    agent_type: Optional[str] = None,
    scenario: Optional[str] = None,
) -> AgentRuleSettings:
    row = resolve_rule_settings_row(
        session,
        tenant_id=tenant_id,
        agent_type=agent_type,
        scenario=scenario,
    )
    return to_rule_settings(row) if row else AgentRuleSettings()


def upsert_rule_settings(
    session: Session,
    *,
    tenant_id: int,
    settings: AgentRuleSettings,
    updated_by: Optional[int],
    agent_type: str = GLOBAL_RULE_AGENT_TYPE,
    scenario: str = DEFAULT_RULE_SCENARIO,
    is_active: bool = True,
) -> AgentRuleSetting:
    normalized_agent_type = (agent_type or GLOBAL_RULE_AGENT_TYPE).strip() or GLOBAL_RULE_AGENT_TYPE
    normalized_scenario = (scenario or DEFAULT_RULE_SCENARIO).strip() or DEFAULT_RULE_SCENARIO
    values = settings.model_dump()
    active_rows = list(
        session.scalars(
            select(AgentRuleSetting)
            .where(AgentRuleSetting.tenant_id == tenant_id)
            .where(AgentRuleSetting.agent_type == normalized_agent_type)
            .where(AgentRuleSetting.scenario == normalized_scenario)
            .where(AgentRuleSetting.is_active.is_(True))
        ).all()
    )
    for active_row in active_rows:
        active_row.is_active = False
        active_row.updated_by = updated_by

    latest_version = session.scalar(
        select(func.max(AgentRuleSetting.version))
        .where(AgentRuleSetting.tenant_id == tenant_id)
        .where(AgentRuleSetting.agent_type == normalized_agent_type)
        .where(AgentRuleSetting.scenario == normalized_scenario)
    )
    row = AgentRuleSetting(
        tenant_id=tenant_id,
        agent_type=normalized_agent_type,
        scenario=normalized_scenario,
        version=int(latest_version or 0) + 1,
        is_active=is_active,
        created_by=updated_by,
        updated_by=updated_by,
        **values,
    )
    session.add(row)
    session.flush()
    return row


def list_rule_setting_profiles(
    session: Session,
    *,
    tenant_id: int,
    limit: int = 100,
) -> list[AgentRuleSetting]:
    stmt = (
        select(AgentRuleSetting)
        .where(AgentRuleSetting.tenant_id == tenant_id)
        .order_by(
            AgentRuleSetting.agent_type.asc(),
            AgentRuleSetting.scenario.asc(),
            AgentRuleSetting.version.desc(),
            AgentRuleSetting.id.desc(),
        )
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def create_run_review(
    session: Session,
    *,
    tenant_id: int,
    agent_run_id: int,
    reviewer_user_id: Optional[int],
    review: AgentRunReviewCreate,
) -> AgentRunReview:
    row = AgentRunReview(
        tenant_id=tenant_id,
        agent_run_id=agent_run_id,
        reviewer_user_id=reviewer_user_id,
        outcome=review.outcome,
        usefulness_score=review.usefulness_score,
        accuracy_score=review.accuracy_score,
        accepted_actions_count=review.accepted_actions_count,
        rejected_actions_count=review.rejected_actions_count,
        follow_up_required=review.follow_up_required,
        feedback=review.feedback,
    )
    session.add(row)
    session.flush()
    return row


def list_run_reviews(
    session: Session,
    *,
    tenant_id: int,
    agent_run_id: Optional[int] = None,
    limit: int = 20,
) -> list[AgentRunReview]:
    stmt = select(AgentRunReview).where(AgentRunReview.tenant_id == tenant_id)
    if agent_run_id is not None:
        stmt = stmt.where(AgentRunReview.agent_run_id == agent_run_id)
    stmt = stmt.order_by(AgentRunReview.created_at.desc(), AgentRunReview.id.desc()).limit(limit)
    return list(session.scalars(stmt).all())
