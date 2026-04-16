"""Admin APIs for model routing rules."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import get_current_user, require_role
from repositories import model_routing_repo


router = APIRouter(prefix="/api/admin/model-routing", tags=["模型路由"])


class ModelRoutingRuleRequest(BaseModel):
    scope: str = "global"
    tenant_id: Optional[int] = None
    task_type: str
    preferred_model: str
    fallback_model: Optional[str] = None
    allow_batch: bool = False
    allow_search: bool = False
    allow_high_cost_mode: bool = False
    prompt_version: str = "v1"
    is_active: bool = True


@router.get("")
def list_rules(
    session: Session = Depends(get_db_session),
    _user: User = Depends(require_role("manager")),
):
    rows = []
    for rule in model_routing_repo.list_rules(session):
        rows.append(
            {
                "id": rule.id,
                "scope": rule.scope,
                "tenant_id": rule.tenant_id,
                "task_type": rule.task_type,
                "preferred_model": rule.preferred_model,
                "fallback_model": rule.fallback_model,
                "allow_batch": rule.allow_batch,
                "allow_search": rule.allow_search,
                "allow_high_cost_mode": rule.allow_high_cost_mode,
                "prompt_version": rule.prompt_version,
                "is_active": rule.is_active,
            }
        )
    return rows


@router.put("")
def upsert_rule(
    req: ModelRoutingRuleRequest,
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("admin")),
):
    row = model_routing_repo.upsert_rule(
        session,
        scope=req.scope,
        tenant_id=req.tenant_id,
        task_type=req.task_type,
        preferred_model=req.preferred_model,
        fallback_model=req.fallback_model,
        allow_batch=req.allow_batch,
        allow_search=req.allow_search,
        allow_high_cost_mode=req.allow_high_cost_mode,
        prompt_version=req.prompt_version,
        is_active=req.is_active,
        created_by=user.id,
    )
    return {"id": row.id}
