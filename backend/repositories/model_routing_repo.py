"""Repository for model routing rules."""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.model_routing import ModelRoutingRule


def list_active_rules(
    session: Session, *, task_type: str, tenant_id: Optional[int] = None
) -> List[ModelRoutingRule]:
    stmt = (
        select(ModelRoutingRule)
        .where(ModelRoutingRule.task_type == task_type)
        .where(ModelRoutingRule.is_active.is_(True))
        .order_by(ModelRoutingRule.id.desc())
    )
    if tenant_id is not None:
        stmt = stmt.where(
            (ModelRoutingRule.scope == "global")
            | (
                (ModelRoutingRule.scope == "tenant")
                & (ModelRoutingRule.tenant_id == tenant_id)
            )
        )
    else:
        stmt = stmt.where(ModelRoutingRule.scope == "global")
    return list(session.scalars(stmt).all())


def get_active_rule(
    session: Session, *, task_type: str, tenant_id: Optional[int] = None
) -> Optional[ModelRoutingRule]:
    rules = list_active_rules(session, task_type=task_type, tenant_id=tenant_id)
    for rule in rules:
        if tenant_id is not None and rule.scope == "tenant" and rule.tenant_id == tenant_id:
            return rule
    for rule in rules:
        if rule.scope == "global":
            return rule
    return None


def list_rules(session: Session) -> List[ModelRoutingRule]:
    stmt = select(ModelRoutingRule).order_by(ModelRoutingRule.id.desc())
    return list(session.scalars(stmt).all())


def upsert_rule(
    session: Session,
    *,
    scope: str,
    task_type: str,
    preferred_model: str,
    fallback_model: Optional[str],
    allow_batch: bool,
    allow_search: bool,
    allow_high_cost_mode: bool,
    prompt_version: str,
    tenant_id: Optional[int] = None,
    is_active: bool = True,
    created_by: Optional[int] = None,
) -> ModelRoutingRule:
    stmt = (
        select(ModelRoutingRule)
        .where(ModelRoutingRule.scope == scope)
        .where(ModelRoutingRule.task_type == task_type)
        .where(ModelRoutingRule.tenant_id == tenant_id)
        .limit(1)
    )
    row = session.scalars(stmt).first()
    if row is None:
        row = ModelRoutingRule(
            scope=scope,
            tenant_id=tenant_id,
            task_type=task_type,
            preferred_model=preferred_model,
            fallback_model=fallback_model,
            allow_batch=allow_batch,
            allow_search=allow_search,
            allow_high_cost_mode=allow_high_cost_mode,
            prompt_version=prompt_version,
            is_active=is_active,
            created_by=created_by,
        )
        session.add(row)
    else:
        row.preferred_model = preferred_model
        row.fallback_model = fallback_model
        row.allow_batch = allow_batch
        row.allow_search = allow_search
        row.allow_high_cost_mode = allow_high_cost_mode
        row.prompt_version = prompt_version
        row.is_active = is_active
        row.created_by = created_by
    session.flush()
    return row
