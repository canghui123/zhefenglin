"""Admin APIs for feature flag defaults and tenant overrides."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import require_role
from repositories import plan_repo, subscription_repo, tenant_repo
from services import audit_service
from services.feature_catalog import FEATURE_CATALOG, FEATURE_INDEX, FEATURE_KEYS


router = APIRouter(prefix="/api/admin/feature-flags", tags=["功能开关"])


def _json_loads(value: Optional[str]) -> dict:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def _validate_feature_keys(features: dict[str, object]) -> None:
    invalid_keys = sorted(key for key in features if key not in FEATURE_INDEX)
    if invalid_keys:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "存在未注册的功能键",
                "invalid_keys": invalid_keys,
                "allowed_keys": list(FEATURE_KEYS),
            },
        )


class PlanFeatureUpdateRequest(BaseModel):
    features: dict[str, bool] = Field(default_factory=dict)


class TenantFeatureUpdateRequest(BaseModel):
    features: dict[str, Optional[bool]] = Field(default_factory=dict)


def _build_feature_maps(session: Session) -> tuple[dict[int, dict[str, bool]], dict[int, dict[str, bool]]]:
    plan_map: dict[int, dict[str, bool]] = {}
    tenant_map: dict[int, dict[str, bool]] = {}
    for row in subscription_repo.list_feature_entitlements(session):
        if row.plan_id is not None:
            plan_map.setdefault(row.plan_id, {})[row.feature_key] = bool(row.is_enabled)
        if row.tenant_id is not None:
            tenant_map.setdefault(row.tenant_id, {})[row.feature_key] = bool(row.is_enabled)
    return plan_map, tenant_map


def _build_plan_rows(
    plans: list,
    *,
    plan_entitlements: dict[int, dict[str, bool]],
) -> tuple[list[dict], dict[int, dict[str, bool]], dict[int, object]]:
    rows: list[dict] = []
    features_by_plan_id: dict[int, dict[str, bool]] = {}
    plans_by_id = {plan.id: plan for plan in plans}

    for plan in plans:
        flags = _json_loads(plan.feature_flags_json)
        features = {
            key: plan_entitlements.get(plan.id, {}).get(key, bool(flags.get(key, False)))
            for key in FEATURE_KEYS
        }
        features_by_plan_id[plan.id] = features
        rows.append(
            {
                "plan_id": plan.id,
                "plan_code": plan.code,
                "plan_name": plan.name,
                "features": features,
            }
        )
    return rows, features_by_plan_id, plans_by_id


def _build_tenant_rows(
    session: Session,
    *,
    plan_features: dict[int, dict[str, bool]],
    plans_by_id: dict[int, object],
    tenant_entitlements: dict[int, dict[str, bool]],
) -> list[dict]:
    tenants = {tenant.id: tenant for tenant in tenant_repo.list_tenants(session)}
    rows: list[dict] = []

    for subscription in subscription_repo.list_current_subscriptions(session):
        tenant = tenants.get(subscription.tenant_id)
        plan = plans_by_id.get(subscription.plan_id)
        inherited = plan_features.get(subscription.plan_id, {})
        overrides_raw = tenant_entitlements.get(subscription.tenant_id, {})
        overrides = {
            key: overrides_raw[key] if key in overrides_raw else None for key in FEATURE_KEYS
        }
        effective_features = {
            key: overrides[key] if overrides[key] is not None else inherited.get(key, False)
            for key in FEATURE_KEYS
        }
        rows.append(
            {
                "tenant_id": subscription.tenant_id,
                "tenant_code": tenant.code if tenant is not None else None,
                "tenant_name": tenant.name if tenant is not None else None,
                "plan_code": plan.code if plan is not None else None,
                "plan_name": plan.name if plan is not None else None,
                "overrides": overrides,
                "effective_features": effective_features,
            }
        )

    return rows


def _snapshot(session: Session) -> dict:
    plan_entitlements, tenant_entitlements = _build_feature_maps(session)
    plans = plan_repo.list_plans(session)
    plan_rows, feature_map, plans_by_id = _build_plan_rows(
        plans,
        plan_entitlements=plan_entitlements,
    )
    return {
        "catalog": list(FEATURE_CATALOG),
        "plans": plan_rows,
        "tenants": _build_tenant_rows(
            session,
            plan_features=feature_map,
            plans_by_id=plans_by_id,
            tenant_entitlements=tenant_entitlements,
        ),
    }


def _get_plan_row(session: Session, *, plan_id: int) -> dict:
    snapshot = _snapshot(session)
    for row in snapshot["plans"]:
        if row["plan_id"] == plan_id:
            return row
    raise HTTPException(status_code=404, detail="套餐不存在")


def _get_tenant_row(session: Session, *, tenant_id: int) -> dict:
    snapshot = _snapshot(session)
    for row in snapshot["tenants"]:
        if row["tenant_id"] == tenant_id:
            return row
    raise HTTPException(status_code=404, detail="租户当前无有效订阅")


@router.get("")
def get_feature_flags(
    session: Session = Depends(get_db_session),
    _user: User = Depends(require_role("manager")),
):
    return _snapshot(session)


@router.put("/plans/{plan_code}")
def update_plan_feature_flags(
    plan_code: str,
    req: PlanFeatureUpdateRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("admin")),
):
    _validate_feature_keys(req.features)
    plan = plan_repo.get_plan_by_code(session, plan_code)
    if plan is None:
        raise HTTPException(status_code=404, detail="套餐不存在")

    before = _get_plan_row(session, plan_id=plan.id)
    flags = _json_loads(plan.feature_flags_json)
    for feature_key, is_enabled in req.features.items():
        flags[feature_key] = bool(is_enabled)
        subscription_repo.replace_feature_entitlement(
            session,
            scope="plan",
            plan_id=plan.id,
            feature_key=feature_key,
            is_enabled=bool(is_enabled),
        )
    plan.feature_flags_json = json.dumps(flags, ensure_ascii=False, sort_keys=True)
    session.flush()

    after = _get_plan_row(session, plan_id=plan.id)
    audit_service.record(
        session,
        request,
        action="feature_flags_plan_update",
        tenant_id=None,
        user_id=user.id,
        resource_type="plan",
        resource_id=plan.id,
        before=before,
        after=after,
    )
    return after


@router.put("/tenants/{tenant_id}")
def update_tenant_feature_flags(
    tenant_id: int,
    req: TenantFeatureUpdateRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("admin")),
):
    _validate_feature_keys(req.features)
    tenant = tenant_repo.get_tenant_by_id(session, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="租户不存在")
    subscription = subscription_repo.get_current_subscription(
        session,
        tenant_id=tenant_id,
        active_only=False,
    )
    if subscription is None:
        raise HTTPException(status_code=404, detail="租户当前无有效订阅")

    before = _get_tenant_row(session, tenant_id=tenant_id)
    for feature_key, override in req.features.items():
        subscription_repo.replace_feature_entitlement(
            session,
            scope="tenant",
            tenant_id=tenant_id,
            feature_key=feature_key,
            is_enabled=override,
        )

    after = _get_tenant_row(session, tenant_id=tenant_id)
    audit_service.record(
        session,
        request,
        action="feature_flags_tenant_update",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="tenant",
        resource_id=tenant_id,
        before=before,
        after=after,
    )
    return after
