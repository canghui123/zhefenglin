"""Admin APIs for valuation trigger rules."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import require_role
from repositories import valuation_rule_repo


router = APIRouter(prefix="/api/admin/valuation-rules", tags=["估值触发规则"])


class ValuationRuleRequest(BaseModel):
    scope: str = "global"
    tenant_id: Optional[int] = None
    trigger_type: str
    enabled: bool = True
    trigger_config: dict = Field(default_factory=dict)


@router.get("")
def list_rules(
    session: Session = Depends(get_db_session),
    _user: User = Depends(require_role("manager")),
):
    rows = []
    for rule in valuation_rule_repo.list_rules(session):
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
    user: User = Depends(require_role("admin")),
):
    row = valuation_rule_repo.upsert_rule(
        session,
        scope=req.scope,
        tenant_id=req.tenant_id,
        enabled=req.enabled,
        trigger_type=req.trigger_type,
        trigger_config_json=json.dumps(req.trigger_config, ensure_ascii=False, sort_keys=True),
        created_by=user.id,
    )
    return {"id": row.id}
