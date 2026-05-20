"""Disposal task APIs backed by work_orders."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from db.models.user import User
from db.models.work_order import WorkOrder
from db.session import get_db_session
from dependencies.auth import get_current_user, require_role
from models.tasks import (
    DisposalTaskAssign,
    DisposalTaskComplete,
    DisposalTaskCreate,
    DisposalTaskOut,
    DisposalTaskUpdate,
)
from repositories import sandbox_repo, tenant_repo, user_repo, work_order_repo
from services import audit_service
from services.portfolio_capacity_planner import build_capacity_plan, get_capacity_settings
from services.portfolio_engine import generate_mock_portfolio
from services.tenant_context import get_current_tenant_id

router = APIRouter(
    prefix="/api/tasks",
    tags=["行动中心任务"],
    dependencies=[Depends(get_current_user)],
)


def _loads(value: Optional[str]) -> dict:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def _task_payload(req: DisposalTaskCreate | DisposalTaskUpdate) -> dict:
    data = req.model_dump(exclude_none=True)
    return {
        key: data[key]
        for key in (
            "owner_user_id",
            "expected_recovery",
            "expected_cost",
            "deadline",
            "evidence_files",
        )
        if key in data
    }


def _serialize(row: WorkOrder) -> DisposalTaskOut:
    payload = _loads(row.payload_json)
    result = _loads(row.result_json)
    return DisposalTaskOut(
        id=row.id,
        tenant_id=row.tenant_id,
        task_type=row.order_type,
        status=row.status,
        priority=row.priority,
        title=row.title,
        target_description=row.target_description,
        source_type=row.source_type,
        source_id=row.source_id,
        owner_user_id=payload.get("owner_user_id"),
        expected_recovery=payload.get("expected_recovery"),
        expected_cost=payload.get("expected_cost"),
        deadline=payload.get("deadline"),
        evidence_files=payload.get("evidence_files") or [],
        result_note=result.get("result_note"),
        actual_recovery=result.get("actual_recovery"),
        variance_reason=result.get("variance_reason"),
        payload=payload,
        result=result,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def _get_task_or_404(session: Session, task_id: int, tenant_id: int) -> WorkOrder:
    row = work_order_repo.get_work_order(session, task_id, tenant_id=tenant_id)
    if row is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return row


def _validate_assignee(session: Session, *, owner_user_id: Optional[int], tenant_id: int) -> None:
    if owner_user_id is None:
        return
    owner = user_repo.get_user_by_id(session, owner_user_id)
    if owner is None or not owner.is_active:
        raise HTTPException(status_code=400, detail="被分配用户不存在或已禁用")
    if not tenant_repo.has_membership(session, user_id=owner_user_id, tenant_id=tenant_id):
        raise HTTPException(status_code=400, detail="被分配用户不属于当前租户")


@router.get("", response_model=list[DisposalTaskOut], dependencies=[Depends(require_role("operator"))])
def list_tasks(
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=300),
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    rows = work_order_repo.list_work_orders(
        session,
        tenant_id=tenant_id,
        status=status,
        order_type=task_type,
        limit=limit,
    )
    return [_serialize(row) for row in rows]


@router.post("", response_model=DisposalTaskOut, dependencies=[Depends(require_role("operator"))])
def create_task(
    req: DisposalTaskCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    _validate_assignee(session, owner_user_id=req.owner_user_id, tenant_id=tenant_id)
    row = work_order_repo.create_work_order(
        session,
        tenant_id=tenant_id,
        created_by=user.id,
        order_type=req.task_type,
        title=req.title,
        priority=req.priority,
        target_description=req.target_description,
        source_type=req.source_type,
        source_id=req.source_id,
        payload=_task_payload(req),
    )
    audit_service.record(
        session,
        request,
        action="task_create",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="work_order",
        resource_id=row.id,
        after=_serialize(row).model_dump(),
    )
    return _serialize(row)




@router.get("/{task_id:int}", response_model=DisposalTaskOut, dependencies=[Depends(require_role("operator"))])
def get_task(
    task_id: int,
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return _serialize(_get_task_or_404(session, task_id, tenant_id))


@router.patch("/{task_id:int}", response_model=DisposalTaskOut, dependencies=[Depends(require_role("operator"))])
def update_task(
    task_id: int,
    req: DisposalTaskUpdate,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    row = _get_task_or_404(session, task_id, tenant_id)
    before = _serialize(row).model_dump()
    _validate_assignee(session, owner_user_id=req.owner_user_id, tenant_id=tenant_id)
    payload = {**_loads(row.payload_json), **_task_payload(req)}
    result = {
        **_loads(row.result_json),
        **{
            key: value
            for key, value in req.model_dump(exclude_none=True).items()
            if key in {"result_note", "actual_recovery", "variance_reason"}
        },
    }
    work_order_repo.update_work_order(
        row,
        order_type=req.task_type,
        status=req.status,
        priority=req.priority,
        title=req.title,
        target_description=req.target_description,
        payload=payload,
        result=result,
    )
    after = _serialize(row).model_dump()
    audit_service.record(
        session,
        request,
        action="task_update",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="work_order",
        resource_id=row.id,
        before=before,
        after=after,
    )
    return _serialize(row)


@router.post("/{task_id:int}/assign", response_model=DisposalTaskOut, dependencies=[Depends(require_role("operator"))])
def assign_task(
    task_id: int,
    req: DisposalTaskAssign,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    row = _get_task_or_404(session, task_id, tenant_id)
    before = _serialize(row).model_dump()
    _validate_assignee(session, owner_user_id=req.owner_user_id, tenant_id=tenant_id)
    payload = {**_loads(row.payload_json), "owner_user_id": req.owner_user_id}
    work_order_repo.update_work_order(row, status="assigned", payload=payload)
    audit_service.record(
        session,
        request,
        action="task_assign",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="work_order",
        resource_id=row.id,
        before=before,
        after=_serialize(row).model_dump(),
    )
    return _serialize(row)


@router.post("/{task_id:int}/complete", response_model=DisposalTaskOut, dependencies=[Depends(require_role("operator"))])
def complete_task(
    task_id: int,
    req: DisposalTaskComplete,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    row = _get_task_or_404(session, task_id, tenant_id)
    before = _serialize(row).model_dump()
    result = {
        **_loads(row.result_json),
        "actual_recovery": req.actual_recovery,
        "result_note": req.result_note,
        "variance_reason": req.variance_reason,
        "evidence_files": req.evidence_files,
    }
    work_order_repo.update_work_order(row, status="done", result=result)
    audit_service.record(
        session,
        request,
        action="task_complete",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="work_order",
        resource_id=row.id,
        before=before,
        after=_serialize(row).model_dump(),
    )
    return _serialize(row)


@router.post("/generate-from-portfolio", response_model=list[DisposalTaskOut], dependencies=[Depends(require_role("operator"))])
def generate_from_portfolio(
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    data = generate_mock_portfolio()
    plan = build_capacity_plan(data["segments"], get_capacity_settings(session, tenant_id))
    created: list[WorkOrder] = []
    for item in plan.current_month_execution_plan:
        source_id = item.segment_name
        existing = work_order_repo.find_open_by_source(
            session,
            tenant_id=tenant_id,
            source_type="portfolio_capacity_plan",
            source_id=source_id,
            order_type=item.task_type,
        )
        if existing is not None:
            created.append(existing)
            continue
        row = work_order_repo.create_work_order(
            session,
            tenant_id=tenant_id,
            created_by=user.id,
            order_type=item.task_type,
            title=f"{item.strategy_name}：{item.segment_name}",
            priority="high" if item.execution_feasibility >= 0.75 else "medium",
            target_description=f"本月执行{item.selected_count}台，递延{item.deferred_count}台",
            source_type="portfolio_capacity_plan",
            source_id=source_id,
            payload={
                "expected_recovery": item.expected_net_recovery,
                "expected_cost": item.required_cost,
                "capacity_resource_needs": item.resource_needs,
                "selected_count": item.selected_count,
                "deferred_count": item.deferred_count,
            },
        )
        created.append(row)
    audit_service.record(
        session,
        request,
        action="task_generate_from_portfolio",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="work_order",
        after={"count": len(created)},
    )
    return [_serialize(row) for row in created]


def _sandbox_path_payload(row, best_path: str) -> tuple[str, float]:
    path_json = {
        "A": row.path_a_json,
        "B": row.path_b_json,
        "C": row.path_c_json,
        "D": row.path_d_json,
        "E": row.path_e_json,
    }.get(best_path, row.path_c_json)
    path = _loads(path_json)
    if best_path == "B":
        scenarios = path.get("scenarios") or []
        net = max((float(item.get("net_recovery") or 0) for item in scenarios), default=0)
    elif best_path == "A":
        timepoints = path.get("timepoints") or []
        net = max((float(item.get("net_position") or 0) for item in timepoints), default=0)
    elif best_path == "E":
        net = float(path.get("net_recovery") or path.get("risk_adjusted_recovery") or 0)
    else:
        net = float(path.get("net_recovery") or 0)
    return path.get("name") or best_path, net


@router.post("/generate-from-sandbox/{result_id}", response_model=DisposalTaskOut, dependencies=[Depends(require_role("operator"))])
def generate_from_sandbox(
    result_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    row = sandbox_repo.get_sandbox_result_by_id(session, result_id, tenant_id=tenant_id)
    if row is None:
        raise HTTPException(status_code=404, detail="沙盘结果不存在")
    best_path = row.best_path or "C"
    task_type = {
        "A": "collection",
        "B": "litigation",
        "C": "auction",
        "D": "special_procedure",
        "E": "restructure",
    }.get(best_path, "auction")
    path_name, expected_recovery = _sandbox_path_payload(row, best_path)
    existing = work_order_repo.find_open_by_source(
        session,
        tenant_id=tenant_id,
        source_type="sandbox",
        source_id=str(result_id),
        order_type=task_type,
    )
    if existing is not None:
        return _serialize(existing)
    task = work_order_repo.create_work_order(
        session,
        tenant_id=tenant_id,
        created_by=user.id,
        order_type=task_type,
        title=f"沙盘推荐执行：{path_name}",
        priority="high",
        target_description=row.car_description,
        source_type="sandbox",
        source_id=str(result_id),
        payload={
            "expected_recovery": expected_recovery,
            "sandbox_best_path": best_path,
            "overdue_amount": row.overdue_amount,
            "che300_value": row.che300_value,
        },
    )
    audit_service.record(
        session,
        request,
        action="task_generate_from_sandbox",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="work_order",
        resource_id=task.id,
        after=_serialize(task).model_dump(),
    )
    return _serialize(task)
