"""Disposal task APIs backed by work_orders."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import datetime
from uuid import uuid4
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel
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
    TaskEvidenceUploadOut,
    DisposalTaskUpdate,
)
from repositories import sandbox_repo, tenant_repo, user_repo, work_order_repo
from services import audit_service
from services.storage.factory import get_storage
from services.tenant_context import get_current_tenant_id
from api.portfolio import build_real_capacity_plan

MAX_EVIDENCE_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_EVIDENCE_TYPES = {
    "application/pdf": {".pdf"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
}

router = APIRouter(
    prefix="/api/tasks",
    tags=["行动中心任务"],
    dependencies=[Depends(get_current_user)],
)


class TaskAssigneeOut(BaseModel):
    id: int
    email: str
    display_name: Optional[str] = None
    role: str


def _loads(value: Optional[str]) -> dict:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def _merge_evidence_files(*groups: object) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        if not isinstance(group, list):
            continue
        for item in group:
            if not isinstance(item, str) or not item:
                continue
            if item not in seen:
                seen.add(item)
                merged.append(item)
    return merged


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


def _serialize(row: WorkOrder, session: Session | None = None) -> DisposalTaskOut:
    payload = _loads(row.payload_json)
    result = _loads(row.result_json)
    evidence_files = _merge_evidence_files(payload.get("evidence_files"), result.get("evidence_files"))
    owner_user_id = payload.get("owner_user_id")
    owner_user_email = None
    owner_display_name = None
    if session is not None and isinstance(owner_user_id, int):
        owner = user_repo.get_user_by_id(session, owner_user_id)
        if owner is not None and tenant_repo.has_membership(session, user_id=owner.id, tenant_id=row.tenant_id):
            owner_user_email = owner.email
            owner_display_name = owner.display_name
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
        owner_user_id=owner_user_id,
        owner_user_email=owner_user_email,
        owner_display_name=owner_display_name,
        expected_recovery=payload.get("expected_recovery"),
        expected_cost=payload.get("expected_cost"),
        deadline=payload.get("deadline"),
        evidence_files=evidence_files,
        result_note=result.get("result_note"),
        actual_recovery=result.get("actual_recovery"),
        variance_reason=result.get("variance_reason"),
        completed_at=result.get("completed_at"),
        payload=payload,
        result=result,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def _safe_filename(filename: str | None) -> str:
    name = os.path.basename(filename or "evidence")
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    return (name or "evidence")[:120]


def _validate_evidence_file(file: UploadFile, data: bytes) -> tuple[str, str]:
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_EVIDENCE_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 PDF、JPG、PNG、WEBP 证据文件")
    if not data:
        raise HTTPException(status_code=400, detail="证据文件不能为空")
    if len(data) > MAX_EVIDENCE_FILE_BYTES:
        raise HTTPException(status_code=413, detail="证据文件不能超过 10MB")
    safe_name = _safe_filename(file.filename)
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in ALLOWED_EVIDENCE_TYPES[content_type]:
        raise HTTPException(status_code=400, detail="证据文件扩展名与文件类型不匹配")
    return safe_name, content_type


def _append_evidence_file(row: WorkOrder, storage_key: str) -> None:
    payload = _loads(row.payload_json)
    evidence_files = _merge_evidence_files(payload.get("evidence_files"), [storage_key])
    work_order_repo.update_work_order(row, payload={**payload, "evidence_files": evidence_files})


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
    return [_serialize(row, session) for row in rows]


@router.get("/assignees", response_model=list[TaskAssigneeOut], dependencies=[Depends(require_role("operator"))])
def list_assignees(
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    users = user_repo.list_active_users_by_tenant(session, tenant_id)
    return [
        TaskAssigneeOut(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
        )
        for user in users
    ]


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
        after=_serialize(row, session).model_dump(),
    )
    return _serialize(row, session)




@router.get("/{task_id:int}", response_model=DisposalTaskOut, dependencies=[Depends(require_role("operator"))])
def get_task(
    task_id: int,
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return _serialize(_get_task_or_404(session, task_id, tenant_id), session)


@router.post("/{task_id:int}/evidence", response_model=TaskEvidenceUploadOut, dependencies=[Depends(require_role("operator"))])
async def upload_task_evidence(
    task_id: int,
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    row = _get_task_or_404(session, task_id, tenant_id)
    data = await file.read(MAX_EVIDENCE_FILE_BYTES + 1)
    safe_name, content_type = _validate_evidence_file(file, data)
    storage_key = f"tasks/{tenant_id}/{task_id}/evidence/{uuid4()}-{safe_name}"
    stored = get_storage().put_bytes(storage_key, data, content_type=content_type)
    before = _serialize(row, session).model_dump()
    _append_evidence_file(row, stored.key)
    audit_service.record(
        session,
        request,
        action="task_evidence_upload",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="work_order",
        resource_id=row.id,
        before=before,
        after=_serialize(row, session).model_dump(),
    )
    return TaskEvidenceUploadOut(
        storage_key=stored.key,
        filename=safe_name,
        content_type=stored.content_type,
        size=stored.size,
    )


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
    before = _serialize(row, session).model_dump()
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
    after = _serialize(row, session).model_dump()
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
    return _serialize(row, session)


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
    before = _serialize(row, session).model_dump()
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
        after=_serialize(row, session).model_dump(),
    )
    return _serialize(row, session)


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
    before = _serialize(row, session).model_dump()
    payload = _loads(row.payload_json)
    evidence_files = _merge_evidence_files(payload.get("evidence_files"), req.evidence_files)
    if req.evidence_files:
        payload = {**payload, "evidence_files": evidence_files}
    result = {
        **_loads(row.result_json),
        "actual_recovery": req.actual_recovery,
        "result_note": req.result_note,
        "variance_reason": req.variance_reason,
        "evidence_files": evidence_files,
        "completed_at": datetime.utcnow().isoformat(),
    }
    work_order_repo.update_work_order(row, status="done", payload=payload, result=result)
    audit_service.record(
        session,
        request,
        action="task_complete",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="work_order",
        resource_id=row.id,
        before=before,
        after=_serialize(row, session).model_dump(),
    )
    return _serialize(row, session)


@router.post("/generate-from-portfolio", response_model=list[DisposalTaskOut], dependencies=[Depends(require_role("operator"))])
def generate_from_portfolio(
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    plan = build_real_capacity_plan(session, tenant_id)
    if plan.data_source != "real_portfolio":
        raise HTTPException(status_code=400, detail=plan.empty_reason or "暂无真实组合数据，无法从产能计划生成任务")
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
    return [_serialize(row, session) for row in created]


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
        return _serialize(existing, session)
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
        after=_serialize(task, session).model_dump(),
    )
    return _serialize(task, session)
