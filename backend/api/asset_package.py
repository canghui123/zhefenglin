"""模块1：资产包买断AI定价API"""

import os
import json
from datetime import date

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel

from config import settings
from database import get_connection
from models.asset import PricingParameters, PackageCalculationResult
from services.excel_parser import parse_excel
from services.che300_client import batch_valuation
from services.pricing_engine import calculate_package
from services.depreciation import predict_depreciation

router = APIRouter(prefix="/api/asset-package", tags=["资产包定价"])


@router.post("/upload")
async def upload_excel(file: UploadFile = File(...)):
    """上传Excel资产包，返回解析结果"""
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="仅支持.xlsx或.xls文件")

    os.makedirs(settings.upload_dir, exist_ok=True)

    # 先插入数据库拿到 package_id，用它做唯一文件名，避免同名覆盖和路径穿越
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO asset_packages (name, upload_filename, total_assets) VALUES (?, ?, ?)",
        (file.filename, "", 0),
    )
    package_id = cursor.lastrowid
    conn.commit()

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
        conn.execute("DELETE FROM asset_packages WHERE id = ?", (package_id,))
        conn.commit()
        conn.close()
        raise HTTPException(status_code=400, detail="Excel解析失败，请检查文件格式")

    # 更新数据库：存磁盘文件名和解析行数
    conn.execute(
        "UPDATE asset_packages SET upload_filename = ?, total_assets = ? WHERE id = ?",
        (disk_name, result.success_rows, package_id),
    )
    conn.commit()
    conn.close()

    return {
        "package_id": package_id,
        "filename": file.filename,
        "parse_result": result.model_dump(),
    }


class CalculateRequest(BaseModel):
    package_id: int
    parameters: PricingParameters = PricingParameters()


@router.post("/calculate", response_model=PackageCalculationResult)
async def calculate(req: CalculateRequest):
    """对已上传的资产包运行定价计算"""
    conn = get_connection()
    pkg = conn.execute("SELECT * FROM asset_packages WHERE id = ?", (req.package_id,)).fetchone()
    conn.close()

    if not pkg:
        raise HTTPException(status_code=404, detail="资产包不存在")

    file_path = os.path.join(settings.upload_dir, pkg["upload_filename"])
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

    valuations = await batch_valuation(val_items)

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

    depreciation_rates = await predict_depreciation(dep_items)

    # 4. 运行定价引擎
    result = calculate_package(assets, req.parameters, valuations, depreciation_rates)
    result.package_id = req.package_id

    # 5. 保存结果
    conn = get_connection()
    conn.execute(
        "UPDATE asset_packages SET parameters_json = ?, results_json = ? WHERE id = ?",
        (req.parameters.model_dump_json(), result.model_dump_json(), req.package_id),
    )
    conn.commit()
    conn.close()

    return result


@router.get("/{package_id}")
async def get_package(package_id: int):
    """获取资产包详情及计算结果"""
    conn = get_connection()
    pkg = conn.execute("SELECT * FROM asset_packages WHERE id = ?", (package_id,)).fetchone()
    conn.close()

    if not pkg:
        raise HTTPException(status_code=404, detail="资产包不存在")

    result_data = None
    if pkg["results_json"]:
        result_data = json.loads(pkg["results_json"])

    return {
        "id": pkg["id"],
        "name": pkg["name"],
        "total_assets": pkg["total_assets"],
        "created_at": pkg["created_at"],
        "results": result_data,
    }


@router.get("/list/all")
async def list_packages():
    """列出所有资产包"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, name, total_assets, created_at FROM asset_packages ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
