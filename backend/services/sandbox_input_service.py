"""Input enrichment and spreadsheet parsing for inventory sandbox."""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Optional

import pandas as pd
from sqlalchemy.orm import Session

from models.simulation import (
    SandboxBatchImportPreview,
    SandboxBatchImportRow,
    SandboxInput,
)
from services.che300_client import get_valuation, get_valuation_by_vin
from services.sandbox_simulator import (
    suggest_auction_discount_rate,
    suggest_redefault_rate_from_history,
)


SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv"}

FIELD_ALIASES: dict[str, list[str]] = {
    "car_description": ["车辆描述", "车型", "品牌型号", "车辆", "车辆型号", "车型名称"],
    "vin": ["vin", "VIN", "车架号", "车辆识别代码", "识别代码"],
    "license_plate": ["车牌", "车牌号", "牌照", "号牌号码"],
    "first_registration": ["首次上牌", "上牌日期", "初登日期", "注册日期", "first_registration"],
    "mileage_km": ["里程", "表显里程", "公里数", "行驶里程"],
    "entry_date": ["入库日期", "评估日期", "入库/评估日期", "处置日期"],
    "overdue_bucket": ["逾期阶段", "逾期分段", "M值", "逾期桶"],
    "overdue_days": ["逾期天数", "DPD", "逾期日数"],
    "overdue_amount": ["逾期金额", "欠款金额", "风险敞口", "EAD", "未偿金额"],
    "che300_value": ["当前车300估值", "车300估值", "车辆估值", "估值", "市场价"],
    "province": ["省份", "省", "所在省", "资产省份"],
    "city": ["城市", "市", "所在城市", "资产城市"],
    "location": ["资产所在地", "所在地", "地区", "区域", "车辆所在地"],
    "vehicle_type": ["车辆类型", "品牌类型", "能源类型"],
    "vehicle_age_years": ["车龄", "车龄年", "车辆年限"],
    "daily_parking": ["日停车费", "停车费"],
    "recovery_cost": ["收车成本", "拖车成本", "找车成本"],
    "sunk_collection_cost": ["已发生催收成本", "催收沉没成本"],
    "sunk_legal_cost": ["已发生法务成本", "法务沉没成本"],
    "annual_interest_rate": ["逾期年利率", "年利率"],
    "vehicle_recovered": ["车辆是否已回收", "是否收回", "收车状态"],
    "vehicle_in_inventory": ["车辆是否已入库", "是否入库", "入库状态"],
    "debtor_dishonest_enforced": ["失信被执行人", "是否失信", "司法风险"],
    "expected_sale_days": ["预计成交天数", "竞拍周期", "拍卖周期"],
    "auction_discount_rate": ["竞拍折扣比例", "拍卖折扣", "竞拍折扣", "折扣比例"],
    "litigation_lawyer_fee": ["常规诉讼律师费", "诉讼律师费"],
    "litigation_recovery_fee_rate": ["常规诉讼回款比例律师费", "诉讼回款费率"],
    "special_lawyer_fee": ["特别程序律师费", "担保物权律师费"],
    "special_recovery_fee_rate": ["特别程序回款比例律师费", "特别程序回款费率"],
    "restructure_monthly_payment": ["月还款额", "重组月还款额"],
    "restructure_months": ["重组期数", "重组月数", "分期期数"],
    "restructure_redefault_rate": ["再违约率", "重组再违约率"],
    "collection_history_text": ["过往催收记录", "逾期记录", "历史催收记录", "催收备注"],
}

REQUIRED_FIELDS = ["car_description", "entry_date", "overdue_amount", "che300_value"]


@dataclass
class ValuationFill:
    value: Optional[float]
    source: str
    error: Optional[str] = None


def _normalize_header(value: Any) -> str:
    text = str(value).strip().lower()
    return re.sub(r"[\s_\-/:：()（）]+", "", text)


def detect_columns(columns: list[Any]) -> tuple[dict[str, str], list[str]]:
    alias_to_field: dict[str, str] = {}
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases + [field]:
            alias_to_field[_normalize_header(alias)] = field

    detected: dict[str, str] = {}
    used: set[str] = set()
    for col in columns:
        original = str(col).strip()
        field = alias_to_field.get(_normalize_header(col))
        if field and field not in detected:
            detected[field] = original
            used.add(original)
    unmapped = [str(col).strip() for col in columns if str(col).strip() not in used]
    return detected, unmapped


def _clean_cell(value: Any) -> Optional[Any]:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "isoformat") and not isinstance(value, str):
        return value.isoformat()[:10]
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none", "null", "无", "暂无", "空"}:
        return None
    return text


def _text(value: Any, max_length: int = 255) -> Optional[str]:
    cleaned = _clean_cell(value)
    if cleaned is None:
        return None
    return str(cleaned).strip()[:max_length]


def _number(value: Any) -> Optional[float]:
    cleaned = _clean_cell(value)
    if cleaned is None:
        return None
    if isinstance(cleaned, (int, float)):
        return float(cleaned)
    text = str(cleaned).strip()
    multiplier = 1.0
    if text.endswith("万"):
        multiplier = 10000.0
        text = text[:-1]
    text = (
        text.replace(",", "")
        .replace("，", "")
        .replace("¥", "")
        .replace("￥", "")
        .replace("元", "")
        .replace("公里", "")
        .replace("km", "")
        .replace("%", "")
        .strip()
    )
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def _rate(value: Any) -> Optional[float]:
    cleaned = _clean_cell(value)
    if cleaned is None:
        return None
    text = str(cleaned).strip()
    number = _number(cleaned)
    if number is None:
        return None
    if "%" in text or number > 1:
        number = number / 100
    return min(1, max(0, number))


def _bool(value: Any) -> Optional[bool]:
    cleaned = _clean_cell(value)
    if cleaned is None:
        return None
    text = str(cleaned).strip().lower()
    if any(token in text for token in ["是", "已", "true", "yes", "y", "1"]):
        return True
    if any(token in text for token in ["否", "未", "false", "no", "n", "0"]):
        return False
    return None


def _derive_region(location: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not location:
        return None, None
    text = location.strip()
    province = None
    city = None
    province_match = re.search(r"([^省市自治区]+(?:省|自治区|市))", text)
    if province_match:
        province = province_match.group(1)
    city_match = re.search(r"([^省市自治区]+市)", text[province_match.end() if province_match else 0 :])
    if city_match:
        city = city_match.group(1)
    return province, city


def _overdue_bucket(raw_bucket: Optional[str], overdue_days: Optional[float]) -> str:
    text = (raw_bucket or "").upper()
    for prefix, label in {
        "M1": "M1(1-30天)",
        "M2": "M2(31-60天)",
        "M3": "M3(61-90天)",
        "M4": "M4(91-120天)",
        "M5": "M5(121-150天)",
        "M6": "M6+(150天以上)",
    }.items():
        if prefix in text:
            return label
    if overdue_days is None:
        return "M3(61-90天)"
    days = int(overdue_days)
    if days <= 30:
        return "M1(1-30天)"
    if days <= 60:
        return "M2(31-60天)"
    if days <= 90:
        return "M3(61-90天)"
    if days <= 120:
        return "M4(91-120天)"
    if days <= 150:
        return "M5(121-150天)"
    return "M6+(150天以上)"


def _read_dataframe(filename: str, content: bytes) -> pd.DataFrame:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError("仅支持 .xlsx、.xls 或 .csv 文件")
    if ext == ".csv":
        for encoding in ("utf-8-sig", "gbk", "gb18030"):
            try:
                return pd.read_csv(BytesIO(content), encoding=encoding)
            except UnicodeDecodeError:
                continue
        return pd.read_csv(BytesIO(content))
    return pd.read_excel(BytesIO(content))


def _extract(raw: dict[str, Any], detected: dict[str, str], field: str) -> Any:
    column = detected.get(field)
    if not column:
        return None
    return raw.get(column)


async def fill_missing_valuation(
    session: Session,
    inp: SandboxInput,
) -> ValuationFill:
    if inp.che300_value is not None and inp.che300_value > 0:
        return ValuationFill(value=inp.che300_value, source="customer")
    try:
        reg_date = inp.first_registration or inp.entry_date or "2020-01-01"
        mileage = (inp.mileage_km / 10000) if inp.mileage_km else None
        if inp.vin and len(inp.vin) == 17:
            result = await get_valuation_by_vin(
                session,
                inp.vin,
                city_name=inp.city,
                reg_date=reg_date,
                mile_age=mileage,
            )
            source = "che300_vin"
        else:
            result = await get_valuation(
                session,
                model_id=inp.car_description or "unknown",
                registration_date=reg_date,
                mileage=mileage,
            )
            source = "che300_model"
        value = result.medium_price or result.good_price or result.fair_price
        if value:
            inp.che300_value = float(value)
            return ValuationFill(value=float(value), source=source)
    except Exception as exc:
        return ValuationFill(value=None, source="failed", error=str(exc))
    return ValuationFill(value=None, source="failed", error="车300未返回有效估值")


def apply_sandbox_suggestions(inp: SandboxInput) -> None:
    if inp.auction_discount_rate is None or inp.auction_discount_rate <= 0:
        inp.auction_discount_rate, _ = suggest_auction_discount_rate(inp)
        inp.auction_discount_auto = True
    else:
        inp.auction_discount_auto = False
    if inp.restructure_redefault_rate is None:
        inp.restructure_redefault_rate, _ = suggest_redefault_rate_from_history(
            inp.collection_history_text
        )
        inp.redefault_rate_auto = True


async def enrich_sandbox_input(session: Session, inp: SandboxInput) -> ValuationFill:
    valuation = await fill_missing_valuation(session, inp)
    apply_sandbox_suggestions(inp)
    return valuation


def missing_required_fields(inp: SandboxInput) -> list[str]:
    missing: list[str] = []
    if not inp.car_description:
        missing.append("car_description")
    if not inp.entry_date:
        missing.append("entry_date")
    if not inp.overdue_amount or inp.overdue_amount <= 0:
        missing.append("overdue_amount")
    if inp.che300_value is None or inp.che300_value <= 0:
        missing.append("che300_value")
    return missing


async def parse_sandbox_batch_import(
    session: Session,
    *,
    filename: str,
    content: bytes,
) -> SandboxBatchImportPreview:
    df = _read_dataframe(filename, content)
    detected, unmapped = detect_columns(list(df.columns))
    rows: list[SandboxBatchImportRow] = []

    for index, record in df.iterrows():
        row_number = int(index) + 2
        raw = {str(col).strip(): _clean_cell(record[col]) for col in df.columns}
        location = _text(_extract(raw, detected, "location"))
        province, city = _derive_region(location)
        overdue_days = _number(_extract(raw, detected, "overdue_days"))
        car_description = _text(_extract(raw, detected, "car_description")) or ""
        entry_date = _text(_extract(raw, detected, "entry_date")) or ""
        auction_discount = _rate(_extract(raw, detected, "auction_discount_rate"))
        redefault_rate = _rate(_extract(raw, detected, "restructure_redefault_rate"))

        inp = SandboxInput(
            car_description=car_description,
            vin=_text(_extract(raw, detected, "vin"), 80),
            license_plate=_text(_extract(raw, detected, "license_plate"), 40),
            first_registration=_text(_extract(raw, detected, "first_registration"), 20),
            mileage_km=_number(_extract(raw, detected, "mileage_km")),
            entry_date=entry_date,
            overdue_bucket=_overdue_bucket(
                _text(_extract(raw, detected, "overdue_bucket")),
                overdue_days,
            ),
            overdue_amount=_number(_extract(raw, detected, "overdue_amount")) or 0,
            che300_value=_number(_extract(raw, detected, "che300_value")),
            province=_text(_extract(raw, detected, "province")) or province,
            city=_text(_extract(raw, detected, "city")) or city,
            vehicle_type=_text(_extract(raw, detected, "vehicle_type"), 40) or "auto",
            vehicle_age_years=_number(_extract(raw, detected, "vehicle_age_years")) or 3,
            daily_parking=_number(_extract(raw, detected, "daily_parking")) or 30,
            recovery_cost=_number(_extract(raw, detected, "recovery_cost")) or 0,
            sunk_collection_cost=_number(_extract(raw, detected, "sunk_collection_cost")) or 0,
            sunk_legal_cost=_number(_extract(raw, detected, "sunk_legal_cost")) or 0,
            annual_interest_rate=_number(_extract(raw, detected, "annual_interest_rate")) or 24,
            vehicle_recovered=_bool(_extract(raw, detected, "vehicle_recovered")) if _bool(_extract(raw, detected, "vehicle_recovered")) is not None else True,
            vehicle_in_inventory=_bool(_extract(raw, detected, "vehicle_in_inventory")) if _bool(_extract(raw, detected, "vehicle_in_inventory")) is not None else True,
            debtor_dishonest_enforced=_bool(_extract(raw, detected, "debtor_dishonest_enforced")) or False,
            expected_sale_days=int(_number(_extract(raw, detected, "expected_sale_days")) or 7),
            auction_discount_rate=auction_discount,
            auction_discount_auto=auction_discount is None,
            litigation_lawyer_fee=_number(_extract(raw, detected, "litigation_lawyer_fee")) or 5000,
            litigation_recovery_fee_rate=_rate(_extract(raw, detected, "litigation_recovery_fee_rate")) or 0.05,
            special_lawyer_fee=_number(_extract(raw, detected, "special_lawyer_fee")) or 3000,
            special_recovery_fee_rate=_rate(_extract(raw, detected, "special_recovery_fee_rate")) or 0.03,
            restructure_monthly_payment=_number(_extract(raw, detected, "restructure_monthly_payment")) or 0,
            restructure_months=int(_number(_extract(raw, detected, "restructure_months")) or 12),
            restructure_redefault_rate=redefault_rate if redefault_rate is not None else 0.30,
            collection_history_text=_text(_extract(raw, detected, "collection_history_text"), 1000),
            redefault_rate_auto=False,
        )

        valuation = await fill_missing_valuation(session, inp)
        apply_sandbox_suggestions(inp)
        missing = missing_required_fields(inp)
        errors: list[str] = []
        if valuation.error and "che300_value" in missing:
            errors.append(f"自动估值失败：{valuation.error}")
        discount, _ = suggest_auction_discount_rate(inp)
        redefault, _ = suggest_redefault_rate_from_history(inp.collection_history_text)
        rows.append(
            SandboxBatchImportRow(
                row_id=f"row-{row_number}",
                row_number=row_number,
                selected=len(missing) == 0,
                input=inp,
                missing_fields=missing,
                errors=errors,
                raw=raw,
                che300_auto_filled=valuation.source not in {"customer", "failed"},
                che300_source=valuation.source,
                suggested_auction_discount_rate=discount,
                suggested_redefault_rate=redefault,
            )
        )

    return SandboxBatchImportPreview(
        total_rows=len(rows),
        rows=rows,
        detected_columns=detected,
        unmapped_columns=unmapped,
    )
