"""Admin APIs for cost center analytics."""
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import require_role
from services import entitlement_service
from services.cost_center_service import (
    build_overview,
    build_value_dashboard,
    build_tenant_breakdown,
    export_tenant_breakdown_csv,
)
from services.tenant_context import get_current_tenant_id


router = APIRouter(prefix="/api/admin/cost-center", tags=["成本中心"])


@router.get("/overview")
def overview(
    session: Session = Depends(get_db_session),
    _user: User = Depends(require_role("manager")),
):
    return build_overview(session)


@router.get("/tenants")
def tenants(
    session: Session = Depends(get_db_session),
    _user: User = Depends(require_role("manager")),
):
    return build_tenant_breakdown(session)


@router.get("/export")
def export_csv(
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_role("manager")),
):
    entitlement_service.ensure_feature_enabled(
        session, tenant_id=tenant_id, feature_key="audit.export"
    )
    csv_text = export_tenant_breakdown_csv(session)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="cost-center.csv"'},
    )


@router.get("/value-dashboard")
def value_dashboard(
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
    _user: User = Depends(require_role("manager")),
):
    entitlement_service.ensure_feature_enabled(
        session, tenant_id=tenant_id, feature_key="tenant.value_dashboard"
    )
    return build_value_dashboard(session)
