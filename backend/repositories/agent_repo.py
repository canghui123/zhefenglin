"""Repository helpers for AI command center agent records."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models.agent import AgentRecommendation, AgentRun, AgentTask, DecisionAuditLog


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
