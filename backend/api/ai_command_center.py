"""AI command center APIs backed by Agent Orchestrator."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.models.user import User
from db.models.role import role_rank
from db.session import get_db_session
from dependencies.auth import get_current_user, require_role
from errors import BusinessError, Forbidden
from models.ai_command import (
    AgentRunCreate,
    AgentRunOut,
    AiCommandOverview,
    DecisionAuditLogOut,
)
from repositories import agent_repo
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
