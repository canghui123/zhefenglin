"""Repository for valuation trigger rules."""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.valuation_control import ValuationTriggerRule


def list_active_rules(session: Session, *, tenant_id: int) -> List[ValuationTriggerRule]:
    stmt = (
        select(ValuationTriggerRule)
        .where(ValuationTriggerRule.enabled.is_(True))
        .where(
            (ValuationTriggerRule.scope == "global")
            | (
                (ValuationTriggerRule.scope == "tenant")
                & (ValuationTriggerRule.tenant_id == tenant_id)
            )
        )
        .order_by(ValuationTriggerRule.id)
    )
    return list(session.scalars(stmt).all())


def list_rules(session: Session) -> List[ValuationTriggerRule]:
    """所有租户可见的规则集合（仅供平台级脚本/后台使用，勿在租户 API 直接暴露）。"""
    stmt = select(ValuationTriggerRule).order_by(ValuationTriggerRule.id.desc())
    return list(session.scalars(stmt).all())


def list_visible_rules(
    session: Session, *, tenant_id: int
) -> List[ValuationTriggerRule]:
    """当前租户可见的规则：global + 自己的 tenant 规则。"""
    stmt = (
        select(ValuationTriggerRule)
        .where(
            (ValuationTriggerRule.scope == "global")
            | (
                (ValuationTriggerRule.scope == "tenant")
                & (ValuationTriggerRule.tenant_id == tenant_id)
            )
        )
        .order_by(ValuationTriggerRule.id.desc())
    )
    return list(session.scalars(stmt).all())


def upsert_rule(
    session: Session,
    *,
    scope: str,
    trigger_type: str,
    enabled: bool,
    trigger_config_json: Optional[str],
    tenant_id: Optional[int] = None,
    created_by: Optional[int] = None,
) -> ValuationTriggerRule:
    stmt = (
        select(ValuationTriggerRule)
        .where(ValuationTriggerRule.scope == scope)
        .where(ValuationTriggerRule.trigger_type == trigger_type)
        .where(ValuationTriggerRule.tenant_id == tenant_id)
        .limit(1)
    )
    row = session.scalars(stmt).first()
    if row is None:
        row = ValuationTriggerRule(
            scope=scope,
            tenant_id=tenant_id,
            enabled=enabled,
            trigger_type=trigger_type,
            trigger_config_json=trigger_config_json,
            created_by=created_by,
        )
        session.add(row)
    else:
        row.enabled = enabled
        row.trigger_config_json = trigger_config_json
        row.created_by = created_by
    session.flush()
    return row
