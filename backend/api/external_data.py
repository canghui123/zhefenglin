"""External data gateway endpoints.

These endpoints expose normalized signals for future GPS/ETC/violation/judicial
integrations. The first version uses deterministic rule scoring so product
logic can be integrated before real providers are contracted.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import get_current_user, require_role
from models.external_data import (
    ExternalProviderCapability,
    FindCarSignalRequest,
    FindCarSignalResult,
    JudicialRiskRequest,
    JudicialRiskResult,
)
from services import audit_service  # noqa: F401
from services.external_data_gateway import (
    assess_judicial_risk,
    compute_find_car_score,
    list_provider_capabilities,
)
from services.tenant_context import get_current_tenant_id


router = APIRouter(
    prefix="/api/external-data",
    tags=["外部数据生态"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/providers", response_model=list[ExternalProviderCapability])
async def providers():
    return list_provider_capabilities()


@router.post(
    "/find-car-score",
    response_model=FindCarSignalResult,
    dependencies=[Depends(require_role("operator"))],
)
async def find_car_score(
    req: FindCarSignalRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    result = compute_find_car_score(req)
    audit_service.record(
        session,
        request,
        action="external_data.find_car_score",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="external_data_signal",
        after={"score": result.score, "level": result.level},
    )
    return result


@router.post(
    "/judicial-risk",
    response_model=JudicialRiskResult,
    dependencies=[Depends(require_role("operator"))],
)
async def judicial_risk(
    req: JudicialRiskRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    result = assess_judicial_risk(req)
    audit_service.record(
        session,
        request,
        action="external_data.judicial_risk",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="external_data_signal",
        after={
            "risk_level": result.risk_level,
            "score": result.score,
            "collection_blocked": result.collection_blocked,
        },
    )
    return result
