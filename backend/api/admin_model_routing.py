"""Admin APIs for model routing rules.

安全约束：
- 读：仅返回当前租户可见规则（global + 自己的 tenant 规则）。
- 写：scope 强制为 "tenant"、tenant_id 强制为当前租户。
  global 规则由平台级运维脚本/迁移维护。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import require_role
from repositories import model_routing_repo
from services import entitlement_service
from services.tenant_context import get_current_tenant_id


router = APIRouter(prefix="/api/admin/model-routing", tags=["模型路由"])


class ModelRoutingRuleRequest(BaseModel):
    # 为兼容旧前端仍接收字段，服务端会强制覆盖
    scope: Optional[str] = None
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
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_role("manager")),
):
    entitlement_service.ensure_feature_enabled(
        session, tenant_id=tenant_id, feature_key="routing.model_control"
    )
    rows = []
    for rule in model_routing_repo.list_visible_rules(session, tenant_id=tenant_id):
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
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_role("admin")),
):
    entitlement_service.ensure_feature_enabled(
        session, tenant_id=tenant_id, feature_key="routing.model_control"
    )

    if req.scope and req.scope == "global":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="租户管理员不能创建/修改 global 规则",
        )
    if req.tenant_id is not None and req.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="不能为其他租户写入规则",
        )

    row = model_routing_repo.upsert_rule(
        session,
        scope="tenant",
        tenant_id=tenant_id,
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
