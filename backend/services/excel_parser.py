"""Excel资产包解析器 — 灵活列映射 + 字段校验"""

import re
from datetime import datetime, date
from typing import Optional

import pandas as pd

from models.asset import Asset, AssetParseError, AssetParseResult

# 关键词 → 字段名 映射表
COLUMN_KEYWORDS = {
    "car_description": ["车型", "品牌型号", "车辆", "品牌", "车名", "车辆信息", "车辆描述"],
    "vin": ["vin", "VIN", "车架号", "车架", "识别代码", "识别码"],
    "first_registration": ["首次登记", "上牌日期", "登记日期", "注册日期", "首次上牌", "上牌时间"],
    "gps_online": ["gps", "GPS", "定位"],
    "insurance_lapsed": ["脱保", "保险", "交强险"],
    "ownership_transferred": ["过户", "转移"],
    "loan_principal": ["本金", "债权", "贷款金额", "剩余本金", "贷款余额"],
    "buyout_price": ["买断", "折扣价", "收购价", "转让价", "处置价"],
}


def _match_column(header: str) -> Optional[str]:
    """将Excel列名匹配到系统字段"""
    header_clean = header.strip().lower()
    for field, keywords in COLUMN_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in header_clean:
                return field
    return None


def _auto_detect_mapping(columns: list[str]) -> dict[str, str]:
    """自动检测列映射：{Excel列名 → 系统字段名}"""
    mapping = {}
    used_fields = set()
    for col in columns:
        field = _match_column(col)
        if field and field not in used_fields:
            mapping[col] = field
            used_fields.add(field)
    return mapping


def _parse_date(val) -> Optional[date]:
    """尝试解析多种日期格式"""
    if pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val

    val_str = str(val).strip()
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日", "%Y.%m.%d", "%Y%m%d"]:
        try:
            return datetime.strptime(val_str, fmt).date()
        except ValueError:
            continue

    # 尝试提取年份
    year_match = re.search(r"(20\d{2})", val_str)
    if year_match:
        return date(int(year_match.group(1)), 1, 1)
    return None


def _parse_bool(val) -> Optional[bool]:
    """解析布尔值：是/否/在线/离线/1/0"""
    if pd.isna(val):
        return None
    val_str = str(val).strip().lower()
    if val_str in ("是", "在线", "正常", "1", "true", "yes", "有"):
        return True
    if val_str in ("否", "离线", "异常", "0", "false", "no", "无"):
        return False
    return None


def _parse_float(val) -> Optional[float]:
    if pd.isna(val):
        return None
    try:
        cleaned = re.sub(r"[,，元¥\s]", "", str(val))
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def parse_excel(
    file_path: str,
    column_mapping: Optional[dict[str, str]] = None,
    sheet_name: int = 0,
) -> AssetParseResult:
    """解析Excel资产包文件

    Args:
        file_path: Excel文件路径
        column_mapping: 手动指定列映射 {Excel列名: 系统字段名}，为None时自动检测
        sheet_name: 工作表索引
    """
    df = pd.read_excel(file_path, sheet_name=sheet_name)

    if column_mapping is None:
        column_mapping = _auto_detect_mapping(list(df.columns))

    # 反转映射：系统字段名 → Excel列名
    field_to_col = {v: k for k, v in column_mapping.items()}

    assets = []
    errors = []

    for idx, row in df.iterrows():
        row_num = idx + 2  # Excel行号(1-indexed + header)

        # 车型描述（必填）
        car_desc_col = field_to_col.get("car_description")
        car_desc = str(row.get(car_desc_col, "")).strip() if car_desc_col else ""
        if not car_desc or car_desc == "nan":
            errors.append(AssetParseError(row_number=row_num, field="car_description", message="缺少车型描述"))
            continue

        # 解析各字段
        reg_date = None
        if "first_registration" in field_to_col:
            reg_date = _parse_date(row.get(field_to_col["first_registration"]))
            if reg_date is None:
                errors.append(AssetParseError(row_number=row_num, field="first_registration", message="日期格式无法识别"))

        gps = _parse_bool(row.get(field_to_col.get("gps_online", ""), None)) if "gps_online" in field_to_col else None
        insurance = _parse_bool(row.get(field_to_col.get("insurance_lapsed", ""), None)) if "insurance_lapsed" in field_to_col else None
        transferred = _parse_bool(row.get(field_to_col.get("ownership_transferred", ""), None)) if "ownership_transferred" in field_to_col else None

        # VIN码
        vin = None
        if "vin" in field_to_col:
            vin_val = str(row.get(field_to_col["vin"], "")).strip().upper()
            if vin_val and vin_val != "NAN" and len(vin_val) == 17 and vin_val.isalnum():
                vin = vin_val
            elif vin_val and vin_val != "NAN":
                errors.append(AssetParseError(row_number=row_num, field="vin", message=f"VIN码格式不正确: {vin_val}"))

        principal = _parse_float(row.get(field_to_col.get("loan_principal", ""), None)) if "loan_principal" in field_to_col else None
        buyout = _parse_float(row.get(field_to_col.get("buyout_price", ""), None)) if "buyout_price" in field_to_col else None

        assets.append(Asset(
            row_number=row_num,
            car_description=car_desc,
            vin=vin,
            first_registration=reg_date,
            gps_online=gps,
            insurance_lapsed=insurance,
            ownership_transferred=transferred,
            loan_principal=principal,
            buyout_price=buyout,
        ))

    return AssetParseResult(
        assets=assets,
        errors=errors,
        total_rows=len(df),
        success_rows=len(assets),
    )
