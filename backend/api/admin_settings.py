"""Admin APIs for plans and subscriptions."""
from __future__ import annotations

import json
from typing import Any, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import get_current_user, require_role
from repositories import (
    deployment_profile_repo,
    plan_repo,
    subscription_repo,
    tenant_repo,
    user_repo,
)
from services import audit_service, entitlement_service


router = APIRouter(prefix="/api/admin/settings", tags=["商业化设置"])


def _json_loads(value: Optional[str]) -> dict:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


class PlanCreateRequest(BaseModel):
    code: str
    name: str
    billing_cycle_supported: str = "monthly,yearly"
    monthly_price: float = 0
    yearly_price: float = 0
    setup_fee: float = 0
    private_deploy_fee: float = 0
    seat_limit: int = 1
    included_vin_calls: int = 0
    included_condition_pricing_points: int = 0
    included_ai_reports: int = 0
    included_asset_packages: int = 0
    included_sandbox_runs: int = 0
    overage_vin_unit_price: float = 0
    overage_condition_pricing_unit_price: float = 0
    feature_flags: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class PlanUpdateRequest(BaseModel):
    name: Optional[str] = None
    billing_cycle_supported: Optional[str] = None
    monthly_price: Optional[float] = None
    yearly_price: Optional[float] = None
    setup_fee: Optional[float] = None
    private_deploy_fee: Optional[float] = None
    seat_limit: Optional[int] = None
    included_vin_calls: Optional[int] = None
    included_condition_pricing_points: Optional[int] = None
    included_ai_reports: Optional[int] = None
    included_asset_packages: Optional[int] = None
    included_sandbox_runs: Optional[int] = None
    overage_vin_unit_price: Optional[float] = None
    overage_condition_pricing_unit_price: Optional[float] = None
    feature_flags: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class PlanOut(BaseModel):
    id: int
    code: str
    name: str
    billing_cycle_supported: str
    monthly_price: float
    yearly_price: float
    setup_fee: float
    private_deploy_fee: float
    seat_limit: int
    included_vin_calls: int
    included_condition_pricing_points: int
    included_ai_reports: int
    included_asset_packages: int
    included_sandbox_runs: int
    overage_vin_unit_price: float
    overage_condition_pricing_unit_price: float
    feature_flags: dict[str, Any]
    is_active: bool


class SubscriptionUpdateRequest(BaseModel):
    plan_code: str
    status: str = "active"
    monthly_budget_limit: float = 0
    alert_threshold_percent: float = 80


class DeploymentProfileUpsertRequest(BaseModel):
    deployment_mode: Optional[Literal["saas_dedicated", "private_vpc", "on_premise"]] = None
    delivery_status: Optional[Literal["planning", "provisioning", "active", "paused"]] = None
    access_domain: Optional[str] = None
    sso_enabled: Optional[bool] = None
    sso_provider: Optional[str] = None
    sso_login_url: Optional[str] = None
    storage_mode: Optional[Literal["platform_managed", "customer_s3", "hybrid"]] = None
    backup_level: Optional[Literal["standard", "enhanced", "regulated"]] = None
    environment_notes: Optional[str] = None
    handover_notes: Optional[str] = None


class DeploymentProfileOut(BaseModel):
    tenant_id: int
    tenant_code: Optional[str] = None
    tenant_name: Optional[str] = None
    plan_code: Optional[str] = None
    plan_name: Optional[str] = None
    private_config_enabled: bool
    private_config_source: Optional[str] = None
    deployment_mode: Optional[str] = None
    delivery_status: Optional[str] = None
    access_domain: Optional[str] = None
    sso_enabled: Optional[bool] = None
    sso_provider: Optional[str] = None
    sso_login_url: Optional[str] = None
    storage_mode: Optional[str] = None
    backup_level: Optional[str] = None
    environment_notes: Optional[str] = None
    handover_notes: Optional[str] = None
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None


def _plan_out(plan) -> PlanOut:
    return PlanOut(
        id=plan.id,
        code=plan.code,
        name=plan.name,
        billing_cycle_supported=plan.billing_cycle_supported,
        monthly_price=plan.monthly_price,
        yearly_price=plan.yearly_price,
        setup_fee=plan.setup_fee,
        private_deploy_fee=plan.private_deploy_fee,
        seat_limit=plan.seat_limit,
        included_vin_calls=plan.included_vin_calls,
        included_condition_pricing_points=plan.included_condition_pricing_points,
        included_ai_reports=plan.included_ai_reports,
        included_asset_packages=plan.included_asset_packages,
        included_sandbox_runs=plan.included_sandbox_runs,
        overage_vin_unit_price=plan.overage_vin_unit_price,
        overage_condition_pricing_unit_price=plan.overage_condition_pricing_unit_price,
        feature_flags=_json_loads(plan.feature_flags_json),
        is_active=plan.is_active,
    )


def _user_label(user_id: Optional[int], *, session: Session) -> Optional[str]:
    if user_id is None:
        return None
    user = user_repo.get_user_by_id(session, user_id)
    if user is None:
        return None
    return user.display_name or user.email


def _deployment_profile_out(
    *,
    session: Session,
    tenant,
    plan,
    feature_state: dict[str, Any],
    profile,
) -> DeploymentProfileOut:
    return DeploymentProfileOut(
        tenant_id=tenant.id,
        tenant_code=tenant.code,
        tenant_name=tenant.name,
        plan_code=plan.code if plan is not None else None,
        plan_name=plan.name if plan is not None else None,
        private_config_enabled=bool(feature_state.get("enabled")),
        private_config_source=feature_state.get("source"),
        deployment_mode=profile.deployment_mode if profile is not None else None,
        delivery_status=profile.delivery_status if profile is not None else None,
        access_domain=profile.access_domain if profile is not None else None,
        sso_enabled=profile.sso_enabled if profile is not None else None,
        sso_provider=profile.sso_provider if profile is not None else None,
        sso_login_url=profile.sso_login_url if profile is not None else None,
        storage_mode=profile.storage_mode if profile is not None else None,
        backup_level=profile.backup_level if profile is not None else None,
        environment_notes=profile.environment_notes if profile is not None else None,
        handover_notes=profile.handover_notes if profile is not None else None,
        updated_at=profile.updated_at.isoformat() if profile is not None and profile.updated_at else None,
        updated_by=_user_label(profile.updated_by if profile is not None else None, session=session),
    )


def _list_deployment_profile_rows(session: Session) -> list[DeploymentProfileOut]:
    plans = {plan.id: plan for plan in plan_repo.list_plans(session)}
    tenants = {tenant.id: tenant for tenant in tenant_repo.list_tenants(session)}
    profiles = {
        profile.tenant_id: profile for profile in deployment_profile_repo.list_profiles(session)
    }
    rows: list[DeploymentProfileOut] = []
    for subscription in subscription_repo.list_current_subscriptions(session):
        tenant = tenants.get(subscription.tenant_id)
        if tenant is None:
            continue
        plan = plans.get(subscription.plan_id)
        feature_state = entitlement_service.get_effective_feature(
            session,
            tenant_id=tenant.id,
            feature_key="deployment.private_config",
        )
        rows.append(
            _deployment_profile_out(
                session=session,
                tenant=tenant,
                plan=plan,
                feature_state=feature_state,
                profile=profiles.get(tenant.id),
            )
        )
    return rows


def _get_deployment_profile_row(session: Session, *, tenant_id: int) -> DeploymentProfileOut:
    for row in _list_deployment_profile_rows(session):
        if row.tenant_id == tenant_id:
            return row
    raise HTTPException(status_code=404, detail="租户当前无有效订阅")


@router.get("/plans", response_model=list[PlanOut])
def list_plans(
    session: Session = Depends(get_db_session),
    _user: User = Depends(require_role("manager")),
):
    return [_plan_out(plan) for plan in plan_repo.list_plans(session)]


@router.post("/plans", response_model=PlanOut)
def create_plan(
    req: PlanCreateRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("admin")),
):
    row = plan_repo.create_plan(
        session,
        code=req.code,
        name=req.name,
        billing_cycle_supported=req.billing_cycle_supported,
        monthly_price=req.monthly_price,
        yearly_price=req.yearly_price,
        setup_fee=req.setup_fee,
        private_deploy_fee=req.private_deploy_fee,
        seat_limit=req.seat_limit,
        included_vin_calls=req.included_vin_calls,
        included_condition_pricing_points=req.included_condition_pricing_points,
        included_ai_reports=req.included_ai_reports,
        included_asset_packages=req.included_asset_packages,
        included_sandbox_runs=req.included_sandbox_runs,
        overage_vin_unit_price=req.overage_vin_unit_price,
        overage_condition_pricing_unit_price=req.overage_condition_pricing_unit_price,
        feature_flags_json=json.dumps(req.feature_flags, ensure_ascii=False, sort_keys=True),
        is_active=req.is_active,
    )
    audit_service.record(
        session,
        request,
        action="plan_create",
        tenant_id=None,
        user_id=user.id,
        resource_type="plan",
        resource_id=row.id,
        after=req.model_dump(),
    )
    return _plan_out(row)


@router.put("/plans/{plan_id}", response_model=PlanOut)
def update_plan(
    plan_id: int,
    req: PlanUpdateRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("admin")),
):
    fields = req.model_dump(exclude_none=True)
    if "feature_flags" in fields:
        fields["feature_flags_json"] = json.dumps(
            fields.pop("feature_flags"), ensure_ascii=False, sort_keys=True
        )
    row = plan_repo.update_plan(session, plan_id, **fields)
    audit_service.record(
        session,
        request,
        action="plan_update",
        tenant_id=None,
        user_id=user.id,
        resource_type="plan",
        resource_id=plan_id,
        after=fields,
    )
    return _plan_out(row)


@router.get("/subscriptions")
def list_subscriptions(
    session: Session = Depends(get_db_session),
    _user: User = Depends(require_role("manager")),
):
    plans = {plan.id: plan for plan in plan_repo.list_plans(session)}
    tenants = {tenant.id: tenant for tenant in tenant_repo.list_tenants(session)}
    rows = []
    for subscription in subscription_repo.list_current_subscriptions(session):
        plan = plans.get(subscription.plan_id)
        tenant = tenants.get(subscription.tenant_id)
        rows.append(
            {
                "id": subscription.id,
                "tenant_id": subscription.tenant_id,
                "tenant_code": tenant.code if tenant is not None else None,
                "tenant_name": tenant.name if tenant is not None else None,
                "plan_code": plan.code if plan is not None else None,
                "plan_name": plan.name if plan is not None else None,
                "status": subscription.status,
                "monthly_budget_limit": subscription.monthly_budget_limit,
                "alert_threshold_percent": subscription.alert_threshold_percent,
            }
        )
    return rows


@router.put("/subscriptions/{tenant_id}")
def upsert_subscription(
    tenant_id: int,
    req: SubscriptionUpdateRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("admin")),
):
    plan = plan_repo.get_plan_by_code(session, req.plan_code)
    row = subscription_repo.upsert_current_subscription(
        session,
        tenant_id=tenant_id,
        plan_id=plan.id,
        status=req.status,
        monthly_budget_limit=req.monthly_budget_limit,
        alert_threshold_percent=req.alert_threshold_percent,
        created_by=user.id,
    )
    audit_service.record(
        session,
        request,
        action="subscription_upsert",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="subscription",
        resource_id=row.id,
        after=req.model_dump(),
    )
    return {
        "id": row.id,
        "tenant_id": tenant_id,
        "plan_code": req.plan_code,
        "status": row.status,
        "monthly_budget_limit": row.monthly_budget_limit,
        "alert_threshold_percent": row.alert_threshold_percent,
    }


@router.get("/deployment-profiles", response_model=list[DeploymentProfileOut])
def list_deployment_profiles(
    session: Session = Depends(get_db_session),
    _user: User = Depends(require_role("manager")),
):
    return _list_deployment_profile_rows(session)


@router.put("/deployment-profiles/{tenant_id}", response_model=DeploymentProfileOut)
def upsert_deployment_profile(
    tenant_id: int,
    req: DeploymentProfileUpsertRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(require_role("admin")),
):
    tenant = tenant_repo.get_tenant_by_id(session, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="租户不存在")

    entitlement_service.ensure_feature_enabled(
        session,
        tenant_id=tenant_id,
        feature_key="deployment.private_config",
    )
    before = None
    existing = deployment_profile_repo.get_profile_by_tenant_id(session, tenant_id=tenant_id)
    if existing is not None:
        before = _get_deployment_profile_row(session, tenant_id=tenant_id).model_dump()

    fields = req.model_dump(exclude_none=True)
    if existing is None:
        fields.setdefault("created_by", user.id)
    fields["updated_by"] = user.id

    row = deployment_profile_repo.upsert_profile(
        session,
        tenant_id=tenant_id,
        **fields,
    )

    after = _get_deployment_profile_row(session, tenant_id=tenant_id).model_dump()
    audit_service.record(
        session,
        request,
        action="deployment_profile_upsert",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="tenant_deployment_profile",
        resource_id=row.id,
        before=before,
        after=after,
    )
    return DeploymentProfileOut.model_validate(after)
