"""模块1：资产包出让定价API"""

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
from errors import (
    AssetPackageNotFound,
    FileNotFoundError_,
    FileTooLarge,
    InvalidFileFormat,
    ParseError,
    ReportNotGenerated,
)
from models.asset import (
    Asset,
    AssetFieldOverride,
    BuyerOfferAnalysis,
    PricingParameters,
    PackageCalculationResult,
)
from repositories import asset_package_repo
from services import approval_service, audit_service, commercial_policy_service  # noqa: F401
from services.asset_package_pdf import generate_asset_package_pdf
from services.buyer_offer_analysis import analyze_buyer_offer
from services.excel_parser import parse_excel
from services.che300_client import batch_valuation
from services.pricing_engine import build_transfer_report_fallback, calculate_package
from services.job_dispatcher import dispatch_inline_async
from services.llm_client import chat_completion
from services.llm_guardrails import (
    DATA_ISOLATION_NOTICE,
    sanitize_user_dict,
    wrap_as_data,
)
from services.storage.factory import get_storage
from services.tenant_context import get_current_tenant_id
from services import rate_limit_service
from config import settings

router = APIRouter(
    prefix="/api/asset-package",
    tags=["资产包定价"],
    dependencies=[Depends(get_current_user)],
)

# 缺少里程时的年均估算值（万公里/年）
ESTIMATED_ANNUAL_MILEAGE = 2.5

# Excel 文件魔数：xlsx 是 ZIP 容器（PK\x03\x04）；xls 是 OLE2 复合文档（\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1）
_XLSX_MAGIC = b"PK\x03\x04"
_XLS_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _sniff_excel_format(content: bytes) -> Optional[str]:
    """按魔数识别 Excel 格式；返回 'xlsx' / 'xls' / None。"""
    if content.startswith(_XLSX_MAGIC):
        return "xlsx"
    if content.startswith(_XLS_MAGIC):
        return "xls"
    return None


async def _read_upload_with_limit(file: UploadFile, *, max_bytes: int) -> bytes:
    """按块读取并限制总大小；超限立即抛 FileTooLarge，避免大文件撑爆内存。"""
    chunks: list[bytes] = []
    total = 0
    chunk_size = 64 * 1024
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise FileTooLarge(
                detail=f"文件超过上限 {max_bytes // (1024 * 1024)} MB"
            )
        chunks.append(chunk)
    return b"".join(chunks)


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


def _asset_package_type_label(asset_package_type: str) -> str:
    return "在库车资产包" if asset_package_type == "inventory" else "非在库车资产包"


def _build_report_summary_payload(result: PackageCalculationResult) -> dict:
    """Build an LLM-safe summary payload with unambiguous coverage definitions."""
    summary = result.summary
    payload = summary.model_dump(
        exclude={
            "analysis_report",
            # This field means data coverage, not collateral value coverage.
            "valuation_coverage_rate",
            "collateral_coverage_ratio",
        }
    )
    payload.update(
        {
            "valuation_data_coverage_rate_percent": summary.valuation_coverage_rate,
            "valuation_data_coverage_formula": "成功取得车300估值的车辆数 / 资产包车辆总数",
            "collateral_value_coverage_ratio": summary.collateral_coverage_ratio,
            "collateral_value_coverage_rate_percent": (
                round(summary.collateral_coverage_ratio * 100, 2)
                if summary.collateral_coverage_ratio is not None
                else None
            ),
            "collateral_value_coverage_formula": "车300估值合计 / 贷款本金合计",
            "principal_exceeds_collateral_value": (
                summary.total_principal > summary.total_vehicle_valuation
                if summary.total_principal > 0 and summary.total_vehicle_valuation > 0
                else None
            ),
            "uncovered_principal_gap": (
                round(summary.total_principal - summary.total_vehicle_valuation, 2)
                if summary.total_principal > 0 and summary.total_vehicle_valuation > 0
                else None
            ),
        }
    )
    return payload


def _apply_asset_overrides(
    assets: list[Asset],
    overrides: dict[int, AssetFieldOverride],
) -> list[Asset]:
    """Apply user-supplied row-level corrections before valuation and pricing."""
    if not overrides:
        return assets

    patched_assets: list[Asset] = []
    for asset in assets:
        override = overrides.get(asset.row_number)
        if override is None:
            patched_assets.append(asset)
            continue

        patch = override.model_dump(exclude_unset=True, exclude_none=True)
        if "car_description" in patch and not str(patch["car_description"]).strip():
            patch.pop("car_description")
        if patch:
            patched_assets.append(asset.model_copy(update=patch))
        else:
            patched_assets.append(asset)
    return patched_assets


async def _generate_transfer_analysis_report(
    result: PackageCalculationResult,
    *,
    session: Session,
    tenant_id: int,
    user_id: int,
    request_id: Optional[str],
) -> str:
    """调用大模型生成出让方资产包分析报告，失败时回退为模板报告。"""
    fallback = build_transfer_report_fallback(result)
    summary = result.summary
    sample_assets = [
        sanitize_user_dict(
            {
                "row_number": row.row_number,
                "car_description": row.car_description,
                "loan_principal": row.loan_principal,
                "che300_valuation": row.che300_valuation,
                "pricing_basis": row.pricing_basis,
                "recommended_transfer_price_low": row.recommended_transfer_price_low,
                "recommended_transfer_price_mid": row.recommended_transfer_price_mid,
                "recommended_transfer_price_high": row.recommended_transfer_price_high,
                "principal_discount_mid": row.principal_discount_mid,
                "valuation_discount_mid": row.valuation_discount_mid,
                "valuation_confidence_score": row.valuation_confidence_score,
                "valuation_confidence_level": row.valuation_confidence_level,
                "valuation_source": row.valuation_source,
                "valuation_anomaly_tags": row.valuation_anomaly_tags,
                "risk_flags": row.risk_flags,
            },
            text_fields={"car_description"},
        )
        for row in result.assets[:12]
    ]
    summary_payload = sanitize_user_dict(_build_report_summary_payload(result), text_fields=set())
    if summary.asset_package_type == "inventory":
        basis_instruction = (
            "这是在库车资产包。请以车300车辆评估价作为主要定价锚点，解释为什么出让方可以围绕车辆可处置价值报价，"
            "同时结合抵押物价值覆盖率（车300估值合计/贷款本金合计）判断谈判上限和瑕疵披露。"
        )
    else:
        basis_instruction = (
            "这是非在库车资产包。请以债权本金作为主要定价锚点，解释为什么非在库资产要对收车不确定性、周期和执行难度折价，"
            "并用车300车辆评估价校验抵押物覆盖和底层回收支撑。"
        )
    prompt = (
        "请站在汽车金融公司/金融机构出让方角度，撰写一份资产包出让定价分析报告。\n"
        f"资产包类型：{_asset_package_type_label(summary.asset_package_type)}。\n"
        f"{basis_instruction}\n\n"
        "报告必须详细、合理、可直接对合作伙伴展示，并包含以下结构：\n"
        "1. 资产包概览；2. 估值数据完整度与抵押物价值覆盖；3. 推荐出让折扣区间和价格区间；"
        "4. 估值可信度与交易适配度；5. 买方可能压价点与出让方反驳依据；"
        "6. 风险披露；7. 谈判策略与底线建议。\n\n"
        f"汇总数据：\n{wrap_as_data(summary_payload, tag='package_summary')}\n\n"
        f"样本车辆数据（最多前12台）：\n{wrap_as_data(sample_assets, tag='asset_sample')}\n\n"
        "关键口径：valuation_data_coverage_rate_percent 只表示估值数据覆盖完整度，不能称为本金覆盖率；"
        "抵押物价值覆盖率必须使用 collateral_value_coverage_rate_percent，公式为车300估值合计/贷款本金合计。"
        "如果 principal_exceeds_collateral_value 为 true，应说明债权本金高于抵押物估值，诉讼/清收回报可能高于车辆处置，"
        "但仍需结合司法诉讼可行性和执行成本判断。\n"
        "要求：使用人民币金额，给出明确区间，不要声称系统替代人工审批，不要编造未提供的事实。"
    )
    report = await chat_completion(
        system_prompt=(
            "你是汽车金融不良资产包出让定价专家，熟悉金融公司资产包转让、车辆抵押物估值、"
            "买方议价逻辑和风险披露。"
            + DATA_ISOLATION_NOTICE
        ),
        user_prompt=prompt,
        temperature=0.25,
        max_tokens=2200,
        session=session,
        tenant_id=tenant_id,
        user_id=user_id,
        module="asset-pricing",
        task_type="report_generation",
        request_id=request_id,
    )
    if not report or report.startswith("[LLM"):
        return fallback
    return report


@router.post("/upload", dependencies=[Depends(require_role("operator"))])
async def upload_excel(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """上传Excel资产包，返回解析结果"""
    rate_limit_service.enforce_request_limit(
        request,
        scope="asset_package.upload",
        limit=settings.rate_limit_write_max_requests,
    )
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise InvalidFileFormat()

    # 先做大小限制 + 魔数校验，再写存储；扩展名仅用来选 content-type
    content = await _read_upload_with_limit(
        file, max_bytes=settings.upload_excel_max_bytes
    )
    if not content:
        raise InvalidFileFormat(detail="文件为空")

    sniffed = _sniff_excel_format(content)
    if sniffed is None:
        raise InvalidFileFormat(detail="文件内容不是合法的 Excel（.xlsx/.xls）")

    # 以魔数识别出的真实格式为准，防止 rename 攻击
    ext = ".xlsx" if sniffed == "xlsx" else ".xls"

    pkg = asset_package_repo.create_package(
        session,
        tenant_id=tenant_id,
        created_by=user.id,
        name=file.filename,
    )
    package_id = pkg.id
    storage_key = f"pkg_{package_id}{ext}"

    store = get_storage()
    store.put_bytes(
        storage_key,
        content,
        content_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if ext == ".xlsx"
            else "application/vnd.ms-excel"
        ),
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
    # 历史兼容字段：旧前端可能仍回传AI买断价，当前出让定价不再使用。
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


class BuyerOfferAnalysisRequest(BaseModel):
    buyer_offer_price: float = Field(..., gt=0)
    buyer_offer_note: Optional[str] = None

    @field_validator("buyer_offer_note", mode="before")
    @classmethod
    def normalize_note(cls, value):
        if value is None:
            return None
        value = str(value).strip()
        return value or None


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
    rate_limit_service.enforce_request_limit(
        request,
        scope="asset_package.calculate",
        limit=settings.rate_limit_write_max_requests,
    )
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
    approval_granted = False
    if _parameters.advanced_condition_pricing and _parameters.approval_request_id is not None:
        approval_service.validate_for_execution(
            session,
            approval_request_id=_parameters.approval_request_id,
            tenant_id=tenant_id,
            type="condition_pricing",
            related_object_type="asset_package",
            related_object_id=str(req.package_id),
        )
        approval_granted = True
    elif _parameters.advanced_condition_pricing and _parameters.strict_policy:
        commercial_policy_service.preflight_condition_pricing(
            session,
            tenant_id=tenant_id,
            vehicle_value=None,
            profit_margin=None,
            risk_tags=[],
            manual_selected=_parameters.manual_selected,
            approval_mode=_parameters.approval_mode,
            single_task_budget=_parameters.single_task_budget,
            strict_policy=True,
            related_object_type="asset_package",
            related_object_id=str(req.package_id),
        )

    async def _do_calculate():
        ext = ".xlsx" if key.endswith(".xlsx") else ".xls"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name
        try:
            parse_result = parse_excel(tmp_path)
        finally:
            os.remove(tmp_path)
        assets = _apply_asset_overrides(parse_result.assets, _parameters.asset_overrides)
        if not assets:
            raise ValueError("资产包中没有有效资产")

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
                "vehicle_value": a.loan_principal,
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
            approval_granted=approval_granted,
            approval_request_id=_parameters.approval_request_id,
            approval_object_type="asset_package",
            approval_object_id=str(_package_id),
        )
        if approval_granted and _parameters.approval_request_id is not None:
            approval_service.consume_request(
                session,
                approval_request_id=_parameters.approval_request_id,
                consumed_request_id=getattr(request.state, "request_id", None),
            )
            audit_service.record(
                session,
                request,
                action="approval_consume",
                tenant_id=_tenant_id,
                user_id=user.id,
                resource_type="approval_request",
                resource_id=_parameters.approval_request_id,
                after={"source": "asset-package.calculate", "package_id": _package_id},
            )

        result = calculate_package(assets, _parameters, valuations)
        result.package_id = _package_id
        result.summary.analysis_report = await _generate_transfer_analysis_report(
            result,
            session=session,
            tenant_id=_tenant_id,
            user_id=user.id,
            request_id=getattr(request.state, "request_id", None),
        )

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


@router.post(
    "/{package_id}/buyer-offer-analysis",
    response_model=BuyerOfferAnalysis,
    dependencies=[Depends(require_role("operator"))],
)
async def buyer_offer_analysis(
    package_id: int,
    req: BuyerOfferAnalysisRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Analyze a manually entered buyer offer against the system recommendation."""
    rate_limit_service.enforce_request_limit(
        request,
        scope="asset_package.buyer_offer",
        limit=settings.rate_limit_write_max_requests,
    )
    pkg = asset_package_repo.get_package_by_id(
        session, package_id, tenant_id=tenant_id
    )
    if not pkg:
        raise AssetPackageNotFound()
    if not pkg.results_json:
        raise ReportNotGenerated()

    result = PackageCalculationResult.model_validate_json(pkg.results_json)
    analysis = analyze_buyer_offer(
        result,
        buyer_offer_price=req.buyer_offer_price,
        buyer_offer_note=req.buyer_offer_note,
    )
    result.summary.buyer_offer_analysis = analysis
    asset_package_repo.save_package_result(
        session,
        package_id,
        tenant_id=tenant_id,
        parameters_json=pkg.parameters_json,
        results_json=result.model_dump_json(),
    )
    audit_service.record(
        session,
        request,
        action="buyer_offer_analysis",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="asset_package",
        resource_id=package_id,
        after={
            "buyer_offer_price": analysis.buyer_offer_price,
            "buyer_offer_gap_rate": analysis.buyer_offer_gap_rate,
        },
    )
    return analysis


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

    parameters_data = None
    if pkg.parameters_json:
        parameters_data = json.loads(pkg.parameters_json)

    return {
        "id": pkg.id,
        "name": pkg.name,
        "total_assets": pkg.total_assets,
        "created_at": pkg.created_at.isoformat() if pkg.created_at else None,
        "parameters": parameters_data,
        "results": result_data,
    }


@router.get("/{package_id}/report.pdf")
async def download_package_report_pdf(
    package_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Download the latest generated asset package analysis report as PDF."""
    pkg = asset_package_repo.get_package_by_id(
        session, package_id, tenant_id=tenant_id
    )
    if not pkg:
        raise AssetPackageNotFound()
    if not pkg.results_json:
        raise ReportNotGenerated()

    result = PackageCalculationResult.model_validate_json(pkg.results_json)
    pdf_bytes = generate_asset_package_pdf(result)
    audit_service.record(
        session,
        request,
        action="download_pdf",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="asset_package",
        resource_id=package_id,
        after={
            "has_buyer_offer_analysis": result.summary.buyer_offer_analysis is not None,
            "tradeability_level": result.summary.tradeability_level,
        },
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="asset_package_{package_id}_transfer_report.pdf"'
            )
        },
    )


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
