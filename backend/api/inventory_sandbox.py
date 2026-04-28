"""模块2：库存决策沙盘API"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import get_current_user, require_role
from errors import (
    FileNotFoundError_,
    ReportNotGenerated,
    SandboxInputIncomplete,
    SandboxResultNotFound,
)
from models.simulation import (
    SandboxBatchImportPreview,
    SandboxBatchSimulationItem,
    SandboxBatchSimulationRequest,
    SandboxBatchSimulationResult,
    SandboxInput,
    SandboxResult,
    SandboxSuggestionRequest,
    SandboxSuggestionResult,
    PathAResult, PathBResult, PathCResult, PathDResult, PathEResult,
)
from repositories import sandbox_repo
from services import audit_service  # noqa: F401
from services.sandbox_simulator import run_simulation
from services.sandbox_simulator import (
    suggest_auction_discount_rate,
    suggest_redefault_rate_from_history,
)
from services.sandbox_input_service import (
    enrich_sandbox_input,
    missing_required_fields,
    parse_sandbox_batch_import,
)
from services.pdf_generator import generate_report_html
from services.job_dispatcher import dispatch_inline_async
from services.storage.factory import get_storage
from services.tenant_context import get_current_tenant_id

router = APIRouter(
    prefix="/api/sandbox",
    tags=["库存决策沙盘"],
    dependencies=[Depends(get_current_user)],
)


async def _run_and_persist_simulation(
    *,
    inp: SandboxInput,
    request: Optional[Request],
    session: Session,
    user: User,
    tenant_id: int,
):
    if inp.restructure_redefault_rate is None and not inp.collection_history_text:
        raise SandboxInputIncomplete(
            "再违约率填写为“无”时，请先输入该客户过往催收记录或逾期记录，系统会据此建议再违约率。"
        )

    await enrich_sandbox_input(session, inp)
    missing = missing_required_fields(inp)
    if missing:
        labels = {
            "car_description": "车辆描述",
            "entry_date": "入库/评估日期",
            "overdue_amount": "逾期金额",
            "che300_value": "车300估值",
        }
        readable = "、".join(labels.get(item, item) for item in missing)
        raise SandboxInputIncomplete(f"仍缺少必要字段：{readable}，请补充后再模拟。")

    result = run_simulation(inp, session=session, tenant_id=tenant_id)

    row = sandbox_repo.create_sandbox_result(
        session,
        tenant_id=tenant_id,
        created_by=user.id,
        car_description=inp.car_description,
        entry_date=inp.entry_date,
        overdue_amount=inp.overdue_amount,
        che300_value=inp.che300_value or 0,
        daily_parking=inp.daily_parking,
        input_json=inp.model_dump_json(),
        path_a_json=result.path_a.model_dump_json(),
        path_b_json=result.path_b.model_dump_json(),
        path_c_json=result.path_c.model_dump_json(),
        path_d_json=result.path_d.model_dump_json(),
        path_e_json=result.path_e.model_dump_json(),
        recommendation=result.recommendation,
        best_path=result.best_path,
    )
    result.id = row.id

    audit_service.record(
        session,
        request,
        action="simulate",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="sandbox_result",
        resource_id=row.id,
        after={
            "best_path": row.best_path,
            "che300_auto_filled": inp.che300_value is not None,
            "auction_discount_rate": inp.auction_discount_rate,
        },
    )

    return result


@router.post(
    "/simulate",
    response_model=SandboxResult,
    dependencies=[Depends(require_role("operator"))],
)
async def simulate(
    inp: SandboxInput,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """运行五路径模拟"""
    return await _run_and_persist_simulation(
        inp=inp,
        request=request,
        session=session,
        user=user,
        tenant_id=tenant_id,
    )


@router.post(
    "/suggestions",
    response_model=SandboxSuggestionResult,
    dependencies=[Depends(require_role("operator"))],
)
async def get_sandbox_suggestions(req: SandboxSuggestionRequest):
    """Suggest auction discount / re-default risk when the user selects “无”."""
    inp = SandboxInput(
        car_description=req.car_description or "待补充车辆",
        entry_date="2026-01-01",
        overdue_bucket=req.overdue_bucket,
        overdue_amount=req.overdue_amount,
        che300_value=req.che300_value or 0,
        vehicle_type=req.vehicle_type,
        vehicle_age_years=req.vehicle_age_years,
        vehicle_recovered=req.vehicle_recovered,
        vehicle_in_inventory=req.vehicle_in_inventory,
        collection_history_text=req.collection_history_text,
    )
    discount, discount_note = suggest_auction_discount_rate(inp)
    redefault = None
    redefault_note = None
    if req.collection_history_text:
        redefault, redefault_note = suggest_redefault_rate_from_history(
            req.collection_history_text
        )
    return SandboxSuggestionResult(
        auction_discount_rate=discount,
        auction_discount_note=discount_note,
        redefault_rate=redefault,
        redefault_rate_note=redefault_note,
    )


@router.post(
    "/import-preview",
    response_model=SandboxBatchImportPreview,
    dependencies=[Depends(require_role("operator"))],
)
async def import_preview(
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
):
    """Parse a customer spreadsheet into editable sandbox rows."""
    content = await file.read()
    return await parse_sandbox_batch_import(
        session,
        filename=file.filename or "sandbox-import.csv",
        content=content,
    )


@router.post(
    "/batch-simulate",
    response_model=SandboxBatchSimulationResult,
    dependencies=[Depends(require_role("operator"))],
)
async def batch_simulate(
    req: SandboxBatchSimulationRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Run sandbox simulation for selected imported rows."""
    results: list[SandboxBatchSimulationItem] = []
    for row in req.rows:
        if not row.selected:
            continue
        try:
            result = await _run_and_persist_simulation(
                inp=SandboxInput.model_validate(row.input.model_dump()),
                request=request,
                session=session,
                user=user,
                tenant_id=tenant_id,
            )
            results.append(
                SandboxBatchSimulationItem(
                    row_id=row.row_id,
                    row_number=row.row_number,
                    status="success",
                    result=result,
                )
            )
        except Exception as exc:
            results.append(
                SandboxBatchSimulationItem(
                    row_id=row.row_id,
                    row_number=row.row_number,
                    status="error",
                    error=getattr(exc, "message", str(exc)),
                )
            )
    success_rows = sum(1 for item in results if item.status == "success")
    error_rows = len(results) - success_rows
    return SandboxBatchSimulationResult(
        total_rows=len(results),
        success_rows=success_rows,
        error_rows=error_rows,
        results=results,
    )


@router.get("/{result_id}")
async def get_result(
    result_id: int,
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """获取模拟结果"""
    import json

    row = sandbox_repo.get_sandbox_result_by_id(
        session, result_id, tenant_id=tenant_id
    )
    if row is None:
        raise SandboxResultNotFound()

    return {
        "id": row.id,
        "car_description": row.car_description,
        "entry_date": row.entry_date,
        "overdue_amount": row.overdue_amount,
        "che300_value": row.che300_value,
        "input": json.loads(row.input_json) if row.input_json else None,
        "path_a": json.loads(row.path_a_json) if row.path_a_json else None,
        "path_b": json.loads(row.path_b_json) if row.path_b_json else None,
        "path_c": json.loads(row.path_c_json) if row.path_c_json else None,
        "path_d": json.loads(row.path_d_json) if row.path_d_json else None,
        "path_e": json.loads(row.path_e_json) if row.path_e_json else None,
        "recommendation": row.recommendation,
        "best_path": row.best_path,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.post(
    "/{result_id}/report",
    status_code=202,
    dependencies=[Depends(require_role("operator"))],
)
async def generate_report(
    result_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """生成PDF报告（异步任务，返回 job_id）"""
    row = sandbox_repo.get_sandbox_result_by_id(
        session, result_id, tenant_id=tenant_id
    )
    if row is None:
        raise SandboxResultNotFound()

    # 从保存的完整数据重建SandboxResult
    if row.input_json:
        inp = SandboxInput.model_validate_json(row.input_json)
    else:
        inp = SandboxInput(
            car_description=row.car_description,
            entry_date=row.entry_date,
            overdue_amount=row.overdue_amount,
            che300_value=row.che300_value,
            daily_parking=row.daily_parking,
        )

    result = SandboxResult(
        id=row.id,
        input=inp,
        path_a=PathAResult.model_validate_json(row.path_a_json),
        path_b=PathBResult.model_validate_json(row.path_b_json),
        path_c=PathCResult.model_validate_json(row.path_c_json),
        path_d=(
            PathDResult.model_validate_json(row.path_d_json)
            if row.path_d_json
            else run_simulation(inp, session=session, tenant_id=tenant_id).path_d
        ),
        path_e=(
            PathEResult.model_validate_json(row.path_e_json)
            if row.path_e_json
            else run_simulation(inp, session=session, tenant_id=tenant_id).path_e
        ),
        recommendation=row.recommendation,
        best_path=row.best_path or "C",
    )

    # Capture for closure
    _result_id = result_id
    _tenant_id = tenant_id

    async def _do_report():
        html = await generate_report_html(result)

        report_key = f"reports/sandbox_{_result_id}.html"
        store = get_storage()
        store.put_bytes(report_key, html.encode("utf-8"), content_type="text/html")
        sandbox_repo.update_report_storage_key(
            session, _result_id, tenant_id=_tenant_id, storage_key=report_key
        )
        return {"result_id": _result_id, "storage_key": report_key}

    job = await dispatch_inline_async(
        session,
        tenant_id=tenant_id,
        requested_by=user.id,
        job_type="report",
        payload={"result_id": result_id},
        fn=_do_report,
    )

    audit_service.record(
        session,
        request,
        action="report",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="sandbox_result",
        resource_id=result_id,
        after={"job_id": job.id},
    )

    return {"job_id": job.id, "status": job.status}


@router.get("/{result_id}/report/download")
async def download_report(
    result_id: int,
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Authorized download of a previously generated report."""
    row = sandbox_repo.get_sandbox_result_by_id(
        session, result_id, tenant_id=tenant_id
    )
    if row is None:
        raise SandboxResultNotFound()

    key = row.report_storage_key
    if not key:
        raise ReportNotGenerated()

    store = get_storage()
    presigned = store.build_download_url(key)
    if presigned is not None:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(presigned)

    try:
        data = store.get_bytes(key)
    except FileNotFoundError:
        raise FileNotFoundError_()

    return Response(
        content=data,
        media_type="text/html; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="report_{result_id}.html"'
        },
    )


@router.get("/list/all")
async def list_results(
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """列出当前租户的模拟结果"""
    rows = sandbox_repo.list_sandbox_results(session, tenant_id=tenant_id)
    return [
        {
            "id": r.id,
            "car_description": r.car_description,
            "che300_value": r.che300_value,
            "recommendation": r.recommendation,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
