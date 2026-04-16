"""模块1：资产包买断AI定价API"""

import json
import os
import tempfile
from datetime import date
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
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
from services.pricing_engine import calculate_package, _pick_condition_price
from services.depreciation import predict_depreciation
from services.job_dispatcher import dispatch_inline_async
from services.llm_client import chat_completion
from services.storage.factory import get_storage
from services.tenant_context import get_current_tenant_id

router = APIRouter(
    prefix="/api/asset-package",
    tags=["资产包定价"],
    dependencies=[Depends(get_current_user)],
)

# 缺少里程时的年均估算值（万公里/年）
ESTIMATED_ANNUAL_MILEAGE = 2.5


def _estimate_mileage(mileage: Optional[float], first_registration: Optional[date]) -> Optional[float]:
    """里程缺失时按上牌年限估算：每年 2.5 万公里

    Returns: (估算后的里程, 是否是估算值)
    """
    if mileage is not None and mileage > 0:
        return mileage
    if first_registration is None:
        return None
    today = date.today()
    years = (today - first_registration).days / 365.25
    years = max(years, 0)
    return round(years * ESTIMATED_ANNUAL_MILEAGE, 2)


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
    # ai_suggest 模式下，前端把 AI 建议的买断价回传（{row_number: buyout_price}）
    ai_buyout_overrides: Optional[dict[int, float]] = Field(default=None)

    @field_validator("ai_buyout_overrides", mode="before")
    @classmethod
    def validate_overrides(cls, overrides):
        if overrides is None:
            return None
        cleaned: dict[int, float] = {}
        for row_number, price in overrides.items():
            normalized_price = float(price)
            if normalized_price <= 0:
                raise ValueError("ai_buyout_overrides 必须全部为正数")
            cleaned[int(row_number)] = normalized_price
        return cleaned


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
    _overrides = req.ai_buyout_overrides or {}

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

        # ai_suggest 策略：把前端回传的 AI 建议买断价写入 asset
        if _parameters.buyout_strategy == "ai_suggest" and _overrides:
            for a in assets:
                if a.row_number in _overrides:
                    a.buyout_price = _overrides[a.row_number]

        val_items = []
        for a in assets:
            # reg_date 使用 YYYY-MM 格式，车300 API 要求
            if a.first_registration:
                reg_date = f"{a.first_registration.year}-{a.first_registration.month:02d}"
            else:
                reg_date = None  # 不传让 API 按年限估算
            # 里程缺失时按年均 2.5 万公里估算
            effective_mileage = _estimate_mileage(a.mileage, a.first_registration)
            risk_tags = []
            if a.insurance_lapsed:
                risk_tags.append("insurance_lapsed")
            if a.ownership_transferred:
                risk_tags.append("ownership_transferred")
            if a.gps_online is False:
                risk_tags.append("gps_offline")
            val_items.append({
                "row_number": a.row_number,
                "vin": a.vin,
                "model_id": f"mock_{a.row_number}",
                "registration_date": reg_date,
                "mileage": effective_mileage,  # 万公里，关键估值参数
                "vehicle_value": a.buyout_price or a.loan_principal,
                "risk_tags": risk_tags,
                "manual_selected": _parameters.manual_selected,
                "approval_mode": _parameters.approval_mode,
            })
        # 把用户选择的车况透传给车300（默认 good）
        valuations = await batch_valuation(
            session,
            val_items,
            condition=_parameters.vehicle_condition or "good",
            tenant_id=_tenant_id,
            user_id=user.id,
            module="asset-pricing",
            request_id=getattr(request.state, "request_id", None),
            valuation_level=(
                "condition_pricing" if _parameters.advanced_condition_pricing else "basic"
            ),
            single_task_budget=_parameters.single_task_budget,
            manual_selected=_parameters.manual_selected,
            approval_mode=_parameters.approval_mode,
            strict_policy=_parameters.strict_policy,
        )

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

        result = calculate_package(assets, _parameters, valuations, depreciation_rates)
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


class SuggestBuyoutRequest(BaseModel):
    package_id: int
    vehicle_condition: str = "good"  # excellent/good/normal
    advanced_condition_pricing: bool = False
    manual_selected: bool = False
    approval_mode: bool = False
    strict_policy: bool = False
    single_task_budget: Optional[float] = None


@router.post("/suggest-buyout", dependencies=[Depends(require_role("operator"))])
async def suggest_buyout(
    req: SuggestBuyoutRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """AI建议每台车的买断价区间（ai_suggest策略使用）

    流程：
    1. 读取已上传的Excel
    2. 调用车300获取每台车估值
    3. 让LLM综合年限、里程、车况风险给出买断价建议区间
    """
    pkg = asset_package_repo.get_package_by_id(session, req.package_id, tenant_id=tenant_id)
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
        raise ParseError()

    # 批量估值，把车况透传给车300；里程缺失按年均 2.5 万公里估算
    val_items = []
    for a in assets:
        reg_date = f"{a.first_registration.year}-{a.first_registration.month:02d}" if a.first_registration else None
        effective_mileage = _estimate_mileage(a.mileage, a.first_registration)
        risk_tags = []
        if a.insurance_lapsed:
            risk_tags.append("insurance_lapsed")
        if a.ownership_transferred:
            risk_tags.append("ownership_transferred")
        if a.gps_online is False:
            risk_tags.append("gps_offline")
        val_items.append({
            "row_number": a.row_number,
            "vin": a.vin,
            "model_id": f"mock_{a.row_number}",
            "registration_date": reg_date,
            "mileage": effective_mileage,
            "vehicle_value": a.buyout_price or a.loan_principal,
            "risk_tags": risk_tags,
            "manual_selected": req.manual_selected,
            "approval_mode": req.approval_mode,
        })
    valuations = await batch_valuation(
        session,
        val_items,
        condition=req.vehicle_condition,
        tenant_id=tenant_id,
        user_id=user.id,
        module="asset-pricing",
        request_id=getattr(request.state, "request_id", None),
        valuation_level="condition_pricing" if req.advanced_condition_pricing else "basic",
        single_task_budget=req.single_task_budget,
        manual_selected=req.manual_selected,
        approval_mode=req.approval_mode,
        strict_policy=req.strict_policy,
    )

    # 基于估值给出建议买断价：车300价 × 折扣系数（默认根据车况）
    condition_factor = {"excellent": 0.55, "good": 0.50, "normal": 0.45}.get(req.vehicle_condition, 0.50)

    suggestions = []
    total_mid = 0
    for a in assets:
        val = valuations.get(a.row_number)
        price = _pick_condition_price(val, req.vehicle_condition) if val else None
        if price:
            mid = round(price * condition_factor, -2)
            low = round(mid * 0.85, -2)
            high = round(mid * 1.15, -2)
        else:
            mid = low = high = 0
        total_mid += mid or 0
        effective_mileage = _estimate_mileage(a.mileage, a.first_registration)
        suggestions.append({
            "row_number": a.row_number,
            "car_description": a.car_description,
            "first_registration": a.first_registration.isoformat() if a.first_registration else None,
            "mileage": a.mileage,
            "estimated_mileage": effective_mileage,
            "mileage_is_estimated": a.mileage is None and effective_mileage is not None,
            "che300_valuation": price,
            "suggested_buyout_low": low,
            "suggested_buyout_mid": mid,
            "suggested_buyout_high": high,
        })

    # 让 LLM 给一份整体建议评论
    sample = suggestions[:10]
    prompt = (
        f"以下是某个汽车金融不良资产包的{len(suggestions)}台车辆数据和系统初步建议的买断价（前10台）：\n"
        f"{json.dumps(sample, ensure_ascii=False, indent=2)}\n\n"
        "请作为资深汽车金融处置顾问，对这个资产包的建议买断价策略给出简短评论（200字以内），"
        "包括：整体折价合理性、风险提示、谈判建议。"
    )
    ai_comment = await chat_completion(
        system_prompt="你是汽车金融不良资产处置领域的资深专家，擅长二手车定价和风险评估。",
        user_prompt=prompt,
        max_tokens=500,
        session=session,
        tenant_id=tenant_id,
        user_id=user.id,
        module="asset-pricing",
        task_type="report_generation",
        request_id=getattr(request.state, "request_id", None),
    )

    return {
        "package_id": req.package_id,
        "vehicle_condition": req.vehicle_condition,
        "total_suggested_buyout": round(total_mid, 2),
        "suggestions": suggestions,
        "ai_comment": ai_comment,
    }


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
