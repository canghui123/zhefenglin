"""模块1：资产包买断AI定价API"""

import json
import os
import tempfile

from fastapi import APIRouter, UploadFile, File, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import get_current_user, require_role
from errors import AssetPackageNotFound, FileNotFoundError_, InvalidFileFormat, ParseError
from models.asset import PricingParameters, PackageCalculationResult
from repositories import asset_package_repo
from services import audit_service  # noqa: F401
from services.excel_parser import parse_excel
from services.che300_client import batch_valuation
from services.pricing_engine import calculate_package
from services.depreciation import predict_depreciation
from services.job_dispatcher import dispatch_inline_async
from services.storage.factory import get_storage
from services.tenant_context import get_current_tenant_id

router = APIRouter(
    prefix="/api/asset-package",
    tags=["资产包定价"],
    dependencies=[Depends(get_current_user)],
)


@router.post("/upload", dependencies=[Depends(require_role("operator"))])
async def upload_excel(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """上传Excel资产包，返回解析结果"""
    if not file.filename.endswith((".xlsx", ".xls")):
        raise InvalidFileFormat()

    # 先插入数据库拿到 package_id，用它做唯一文件名，避免同名覆盖
    pkg = asset_package_repo.create_package(
        session,
        tenant_id=tenant_id,
        created_by=user.id,
        name=file.filename,
    )
    package_id = pkg.id

    ext = ".xlsx" if (file.filename or "").endswith(".xlsx") else ".xls"
    storage_key = f"pkg_{package_id}{ext}"

    content = await file.read()

    store = get_storage()
    store.put_bytes(
        storage_key,
        content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # parse_excel needs a filesystem path — write a temp file
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        result = parse_excel(tmp_path)
    except Exception:
        store.delete_object(storage_key)
        asset_package_repo.delete_package(session, package_id, tenant_id=tenant_id)
        raise ParseError()
    finally:
        if "tmp_path" in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)

    # 更新数据库：存 storage_key 和解析行数
    asset_package_repo.update_package_upload(
        session,
        package_id,
        tenant_id=tenant_id,
        upload_filename=storage_key,
        total_assets=result.success_rows,
        storage_key=storage_key,
    )

    audit_service.record(
        session,
        request,
        action="upload",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="asset_package",
        resource_id=package_id,
        after={"filename": file.filename, "rows": result.success_rows},
    )

    return {
        "package_id": package_id,
        "filename": file.filename,
        "parse_result": result.model_dump(),
    }


class CalculateRequest(BaseModel):
    package_id: int
    parameters: PricingParameters = PricingParameters()


@router.post(
    "/calculate",
    status_code=202,
    dependencies=[Depends(require_role("operator"))],
)
async def calculate(
    req: CalculateRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """对已上传的资产包运行定价计算（异步任务）"""
    pkg = asset_package_repo.get_package_by_id(
        session, req.package_id, tenant_id=tenant_id
    )
    if not pkg:
        raise AssetPackageNotFound()

    key = pkg.storage_key or pkg.upload_filename
    if not key:
        raise FileNotFoundError_()

    store = get_storage()
    try:
        data = store.get_bytes(key)
    except FileNotFoundError:
        raise FileNotFoundError_()

    # Capture values needed by the closure
    _package_id = req.package_id
    _parameters = req.parameters
    _tenant_id = tenant_id

    async def _do_calculate():
        ext = ".xlsx" if key.endswith(".xlsx") else ".xls"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            parse_result = parse_excel(tmp_path)
        finally:
            os.remove(tmp_path)
        assets = parse_result.assets
        if not assets:
            raise ValueError("资产包中没有有效资产")

        val_items = []
        for a in assets:
            reg_date = a.first_registration.isoformat() if a.first_registration else "2020-01-01"
            val_items.append({
                "row_number": a.row_number,
                "vin": a.vin,
                "model_id": f"mock_{a.row_number}",
                "registration_date": reg_date,
            })
        valuations = await batch_valuation(session, val_items)

        dep_items = []
        for a in assets:
            val = valuations.get(a.row_number)
            reg_year = a.first_registration.year if a.first_registration else 2020
            dep_items.append({
                "row_number": a.row_number,
                "car_description": a.car_description,
                "valuation": val.medium_price if val and val.medium_price else 0,
                "reg_year": reg_year,
            })
        depreciation_rates = await predict_depreciation(session, dep_items)

        result = calculate_package(
            assets,
            _parameters,
            valuations,
            depreciation_rates,
            session=session,
        )
        result.package_id = _package_id

        asset_package_repo.save_package_result(
            session,
            _package_id,
            tenant_id=_tenant_id,
            parameters_json=_parameters.model_dump_json(),
            results_json=result.model_dump_json(),
        )
        return {"package_id": _package_id, "asset_count": len(assets)}

    job = await dispatch_inline_async(
        session,
        tenant_id=tenant_id,
        requested_by=user.id,
        job_type="calculate",
        payload={"package_id": _package_id},
        fn=_do_calculate,
    )

    audit_service.record(
        session,
        request,
        action="calculate",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="asset_package",
        resource_id=req.package_id,
        after={"job_id": job.id},
    )

    return {"job_id": job.id, "status": job.status}


@router.get("/{package_id}")
async def get_package(
    package_id: int,
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """获取资产包详情及计算结果"""
    pkg = asset_package_repo.get_package_by_id(
        session, package_id, tenant_id=tenant_id
    )

    if not pkg:
        raise AssetPackageNotFound()

    result_data = None
    if pkg.results_json:
        result_data = json.loads(pkg.results_json)

    return {
        "id": pkg.id,
        "name": pkg.name,
        "total_assets": pkg.total_assets,
        "created_at": pkg.created_at.isoformat() if pkg.created_at else None,
        "results": result_data,
    }


@router.get("/{package_id}/download")
async def download_package(
    package_id: int,
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Authorized download of the uploaded Excel file."""
    pkg = asset_package_repo.get_package_by_id(
        session, package_id, tenant_id=tenant_id
    )
    if not pkg:
        raise AssetPackageNotFound()

    key = pkg.storage_key or pkg.upload_filename
    if not key:
        raise FileNotFoundError_()

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
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{pkg.name or key}"'},
    )


@router.get("/list/all")
async def list_packages(
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """列出当前租户的资产包"""
    rows = asset_package_repo.list_packages(session, tenant_id=tenant_id)
    return [
        {
            "id": r.id,
            "name": r.name,
            "total_assets": r.total_assets,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
