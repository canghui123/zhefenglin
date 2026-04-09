"""模块1：资产包买断AI定价API"""

import os
import json

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from config import settings
from db.models.user import User
from db.session import get_db_session
from dependencies.auth import get_current_user, require_role
from models.asset import PricingParameters, PackageCalculationResult
from repositories import asset_package_repo
from services import audit_service  # noqa: F401  (imported as module attribute)
from services.excel_parser import parse_excel
from services.che300_client import batch_valuation
from services.pricing_engine import calculate_package
from services.depreciation import predict_depreciation
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
        raise HTTPException(status_code=400, detail="仅支持.xlsx或.xls文件")

    os.makedirs(settings.upload_dir, exist_ok=True)

    # 先插入数据库拿到 package_id，用它做唯一文件名，避免同名覆盖和路径穿越
    pkg = asset_package_repo.create_package(
        session,
        tenant_id=tenant_id,
        created_by=user.id,
        name=file.filename,
    )
    package_id = pkg.id

    ext = ".xlsx" if (file.filename or "").endswith(".xlsx") else ".xls"
    disk_name = f"pkg_{package_id}{ext}"
    file_path = os.path.join(os.path.realpath(settings.upload_dir), disk_name)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        result = parse_excel(file_path)
    except Exception:
        # 解析失败：清理磁盘文件和数据库孤行
        if os.path.exists(file_path):
            os.remove(file_path)
        asset_package_repo.delete_package(session, package_id, tenant_id=tenant_id)
        raise HTTPException(status_code=400, detail="Excel解析失败，请检查文件格式")

    # 更新数据库：存磁盘文件名和解析行数
    asset_package_repo.update_package_upload(
        session,
        package_id,
        tenant_id=tenant_id,
        upload_filename=disk_name,
        total_assets=result.success_rows,
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
    response_model=PackageCalculationResult,
    dependencies=[Depends(require_role("operator"))],
)
async def calculate(
    req: CalculateRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """对已上传的资产包运行定价计算"""
    pkg = asset_package_repo.get_package_by_id(
        session, req.package_id, tenant_id=tenant_id
    )

    if not pkg:
        raise HTTPException(status_code=404, detail="资产包不存在")

    file_path = os.path.join(settings.upload_dir, pkg.upload_filename or "")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Excel文件已丢失")

    # 1. 重新解析Excel
    parse_result = parse_excel(file_path)
    assets = parse_result.assets

    if not assets:
        raise HTTPException(status_code=400, detail="资产包中没有有效资产")

    # 2. 批量估值（优先使用VIN真实API，无VIN则Mock）
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

    # 3. LLM贬值预测
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

    # 4. 运行定价引擎
    result = calculate_package(assets, req.parameters, valuations, depreciation_rates)
    result.package_id = req.package_id

    # 5. 保存结果
    asset_package_repo.save_package_result(
        session,
        req.package_id,
        tenant_id=tenant_id,
        parameters_json=req.parameters.model_dump_json(),
        results_json=result.model_dump_json(),
    )

    audit_service.record(
        session,
        request,
        action="calculate",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="asset_package",
        resource_id=req.package_id,
        after={"asset_count": len(assets)},
    )

    return result


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
        raise HTTPException(status_code=404, detail="资产包不存在")

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
