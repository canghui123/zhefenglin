"""Resolve the preferred model for a task type."""
from __future__ import annotations

from typing import Optional

from repositories import model_routing_repo


DEFAULT_ROUTE = {
    "scope": "fallback",
    "task_type": "light_task",
    "preferred_model": "qwen-turbo",
    "fallback_model": "qwen-plus",
    "allow_batch": False,
    "allow_search": False,
    "allow_high_cost_mode": False,
    "prompt_version": "v1",
}


def resolve_route(session, *, task_type: str, tenant_id: Optional[int]) -> dict:
    rule = model_routing_repo.get_active_rule(session, task_type=task_type, tenant_id=tenant_id)
    if rule is None:
        route = dict(DEFAULT_ROUTE)
        route["task_type"] = task_type
        return route

    return {
        "scope": rule.scope,
        "task_type": rule.task_type,
        "preferred_model": rule.preferred_model,
        "fallback_model": rule.fallback_model,
        "allow_batch": rule.allow_batch,
        "allow_search": rule.allow_search,
        "allow_high_cost_mode": rule.allow_high_cost_mode,
        "prompt_version": rule.prompt_version,
    }
