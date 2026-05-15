"""Admin APIs for valuation trigger rules.

安全约束：
- 读：仅返回当前租户可见规则（global + 自己的 tenant 规则）。
- 写：scope 强制为 "tenant"、tenant_id 强制为当前租户。
  global 规则由平台级运维脚本/迁移维护，不开放给租户管理员。
"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import require_role
from repositories import valuation_rule_repo
from services.tenant_context import get_current_tenant_id


router = APIRouter(prefix="/api/admin/valuation-rules", tags=["估值触发规则"])


class ValuationRuleRequest(BaseModel):
    # 为兼容旧前端仍接收字段，但会在服务端强制覆盖
    scope: Optional[str] = None
    tenant_id: Optional[int] = None
    trigger_type: str
    enabled: bool = True
    trigger_config: dict = Field(default_factory=dict)


@router.get("")
def list_rules(
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_role("manager")),
):
    rows = []
    for rule in valuation_rule_repo.list_visible_rules(session, tenant_id=tenant_id):
        rows.append(
            {
                "id": rule.id,
                "scope": rule.scope,
                "tenant_id": rule.tenant_id,
                "enabled": rule.enabled,
                "trigger_type": rule.trigger_type,
                "trigger_config": json.loads(rule.trigger_config_json or "{}"),
            }
        )
    return rows


@router.put("")
def upsert_rule(
    req: ValuationRuleRequest,
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
    user: User = Depends(require_role("admin")),
):
    # 请求体中的 scope/tenant_id 仅用于兼容；一律强制绑定到当前租户
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

    row = valuation_rule_repo.upsert_rule(
        session,
        scope="tenant",
        tenant_id=tenant_id,
        enabled=req.enabled,
        trigger_type=req.trigger_type,
        trigger_config_json=json.dumps(req.trigger_config, ensure_ascii=False, sort_keys=True),
        created_by=user.id,
    )
    return {"id": row.id}
