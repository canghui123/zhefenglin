"""模块2：库存决策沙盘API"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import get_current_user, require_role
from models.simulation import (
    SandboxInput, SandboxResult,
    PathAResult, PathBResult, PathCResult, PathDResult, PathEResult,
)
from repositories import sandbox_repo
from services import audit_service  # noqa: F401
from services.sandbox_simulator import run_simulation
from services.pdf_generator import generate_report_html
from services.tenant_context import get_current_tenant_id

router = APIRouter(
    prefix="/api/sandbox",
    tags=["库存决策沙盘"],
    dependencies=[Depends(get_current_user)],
)


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
    result = run_simulation(inp)

    row = sandbox_repo.create_sandbox_result(
        session,
        tenant_id=tenant_id,
        created_by=user.id,
        car_description=inp.car_description,
        entry_date=inp.entry_date,
        overdue_amount=inp.overdue_amount,
        che300_value=inp.che300_value,
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
        after={"best_path": row.best_path},
    )

    return result


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
        raise HTTPException(status_code=404, detail="模拟结果不存在")

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
    response_class=HTMLResponse,
    dependencies=[Depends(require_role("operator"))],
)
async def generate_report(
    result_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """生成PDF报告（返回HTML预览）"""
    row = sandbox_repo.get_sandbox_result_by_id(
        session, result_id, tenant_id=tenant_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="模拟结果不存在")

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
        path_d=PathDResult.model_validate_json(row.path_d_json) if row.path_d_json else run_simulation(inp).path_d,
        path_e=PathEResult.model_validate_json(row.path_e_json) if row.path_e_json else run_simulation(inp).path_e,
        recommendation=row.recommendation,
        best_path=row.best_path or "C",
    )

    html = await generate_report_html(result)

    audit_service.record(
        session,
        request,
        action="report",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="sandbox_result",
        resource_id=result_id,
        after={"format": "html"},
    )

    return HTMLResponse(content=html)


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
