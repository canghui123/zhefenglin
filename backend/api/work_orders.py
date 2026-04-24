"""Execution work order API."""

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import get_current_user, require_role
from errors import WorkOrderNotFound
from models.work_order import WorkOrderCreate, WorkOrderOut, WorkOrderStatusUpdate
from repositories import work_order_repo
from services import audit_service  # noqa: F401
from services.tenant_context import get_current_tenant_id
from services.work_order_service import (
    create_work_order,
    serialize_work_order,
    update_work_order_status,
)


router = APIRouter(
    prefix="/api/work-orders",
    tags=["执行工单"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[WorkOrderOut])
async def list_work_orders(
    status: Optional[str] = Query(default=None),
    order_type: Optional[str] = Query(default=None),
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    rows = work_order_repo.list_work_orders(
        session,
        tenant_id=tenant_id,
        status=status,
        order_type=order_type,
    )
    return [serialize_work_order(row) for row in rows]


@router.post(
    "",
    response_model=WorkOrderOut,
    dependencies=[Depends(require_role("operator"))],
)
async def create_order(
    req: WorkOrderCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    row = create_work_order(
        session,
        tenant_id=tenant_id,
        created_by=user.id,
        req=req,
    )
    audit_service.record(
        session,
        request,
        action="work_order.create",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="work_order",
        resource_id=row.id,
        after=serialize_work_order(row).model_dump(),
    )
    return serialize_work_order(row)


@router.get("/{work_order_id}", response_model=WorkOrderOut)
async def get_order(
    work_order_id: int,
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    row = work_order_repo.get_work_order_by_id(
        session,
        work_order_id,
        tenant_id=tenant_id,
    )
    if row is None:
        raise WorkOrderNotFound()
    return serialize_work_order(row)


@router.put(
    "/{work_order_id}/status",
    response_model=WorkOrderOut,
    dependencies=[Depends(require_role("operator"))],
)
async def update_order_status(
    work_order_id: int,
    req: WorkOrderStatusUpdate,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    before = work_order_repo.get_work_order_by_id(
        session,
        work_order_id,
        tenant_id=tenant_id,
    )
    if before is None:
        raise WorkOrderNotFound()
    before_out = serialize_work_order(before).model_dump()
    row = update_work_order_status(
        session,
        tenant_id=tenant_id,
        work_order_id=work_order_id,
        status=req.status,
        result=req.result,
    )
    after_out = serialize_work_order(row).model_dump()
    audit_service.record(
        session,
        request,
        action="work_order.status_update",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="work_order",
        resource_id=row.id,
        before=before_out,
        after=after_out,
    )
    return serialize_work_order(row)
