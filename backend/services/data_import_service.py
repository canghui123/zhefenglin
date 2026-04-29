"""Parse and stage customer legacy-system exports."""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Optional

import pandas as pd
from sqlalchemy.orm import Session

from db.models.data_import import DataImportBatch, DataImportRow
from models.data_import import (
    DataImportBatchOut,
    DataImportError,
    DataImportRowOut,
    DataImportUploadResult,
)
from repositories import data_import_repo


SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv"}

CANONICAL_FIELDS = [
    "asset_identifier",
    "contract_number",
    "debtor_name",
    "car_description",
    "vin",
    "license_plate",
    "province",
    "city",
    "location",
    "overdue_bucket",
    "overdue_days",
    "overdue_amount",
    "loan_principal",
    "vehicle_value",
    "recovered_status",
    "gps_last_seen",
]

FIELD_ALIASES: dict[str, list[str]] = {
    "asset_identifier": [
        "资产编号",
        "资产ID",
        "资产id",
        "案件编号",
        "账户编号",
        "客户编号",
        "account_id",
        "asset_id",
        "asset identifier",
    ],
    "contract_number": ["合同编号", "合同号", "借据号", "贷款合同号", "contract_no"],
    "debtor_name": ["客户姓名", "债务人", "借款人", "姓名", "客户名称", "debtor"],
    "car_description": ["车型", "品牌型号", "车辆", "车辆描述", "车辆型号", "车型名称"],
    "vin": ["vin", "VIN", "车架号", "车辆识别代码", "识别代码"],
    "license_plate": ["车牌", "牌照", "车牌号", "号牌号码"],
    "province": ["省份", "省", "所在省", "资产省份"],
    "city": ["城市", "市", "所在城市", "资产城市"],
    "location": ["所在地", "资产所在地", "地区", "区域", "车辆所在地"],
    "overdue_bucket": ["逾期阶段", "逾期分段", "逾期桶", "M值", "bucket"],
    "overdue_days": ["逾期天数", "逾期日数", "DPD", "overdue_days"],
    "overdue_amount": ["逾期金额", "欠款金额", "未偿金额", "EAD", "风险敞口", "当前欠款"],
    "loan_principal": ["剩余本金", "本金", "贷款余额", "未还本金"],
    "vehicle_value": ["车辆估值", "车300估值", "市场价", "评估价", "车辆价值"],
    "recovered_status": ["车辆状态", "收车状态", "是否收回", "入库状态", "占有状态"],
    "gps_last_seen": ["GPS时间", "定位时间", "最近定位", "gps_last_seen", "最后GPS时间"],
}

MONEY_FIELDS = {"overdue_amount", "loan_principal", "vehicle_value"}
INTEGER_FIELDS = {"overdue_days"}


@dataclass
class ParsedImport:
    rows: list[dict]
    total_rows: int
    success_rows: int
    error_rows: int
    detected_columns: dict[str, str]
    unmapped_columns: list[str]


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _json_loads(value: Optional[str], default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


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
        return value.isoformat()
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "none", "null"}:
        return None
    return text


def _parse_text(value: Any, *, max_length: int = 255) -> Optional[str]:
    cleaned = _clean_cell(value)
    if cleaned is None:
        return None
    text = str(cleaned).strip()
    return text[:max_length] if text else None


def _parse_number(value: Any, field: str) -> tuple[Optional[int], Optional[str]]:
    cleaned = _clean_cell(value)
    if cleaned is None:
        return None, None
    if isinstance(cleaned, (int, float)):
        number = float(cleaned)
    else:
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
            .replace("天", "")
            .strip()
        )
        try:
            number = float(text) * multiplier
        except ValueError:
            return None, "无法解析为数字"
    if number < 0:
        return None, "不能小于0"
    if field in INTEGER_FIELDS:
        return int(round(number)), None
    return int(round(number)), None


def _normalize_header(value: Any) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[\s_\-/:：()（）]+", "", text)
    return text


def detect_columns(columns: list[Any]) -> tuple[dict[str, str], list[str]]:
    alias_to_field: dict[str, str] = {}
    for field, aliases in FIELD_ALIASES.items():
        values = aliases + [field]
        for alias in values:
            alias_to_field[_normalize_header(alias)] = field

    detected: dict[str, str] = {}
    used_columns: set[str] = set()
    for col in columns:
        original = str(col).strip()
        field = alias_to_field.get(_normalize_header(col))
        if field and field not in detected:
            detected[field] = original
            used_columns.add(original)

    unmapped = [str(col).strip() for col in columns if str(col).strip() not in used_columns]
    return detected, unmapped


def _extract(raw: dict[str, Any], detected_columns: dict[str, str], field: str) -> Any:
    col = detected_columns.get(field)
    if not col:
        return None
    return raw.get(col)


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
    if province is None and city is None and text:
        parts = re.split(r"[\s,，/]+", text)
        if parts:
            province = parts[0] or None
        if len(parts) > 1:
            city = parts[1] or None
    return province, city


def _normalize_overdue_bucket(raw_bucket: Optional[str], overdue_days: Optional[int]) -> Optional[str]:
    text = (raw_bucket or "").upper().replace("（", "(").replace("）", ")").strip()
    bucket_map = {
        "M1": "M1(1-30天)",
        "M2": "M2(31-60天)",
        "M3": "M3(61-90天)",
        "M4": "M4(91-120天)",
        "M5": "M5(121-150天)",
    }
    for key, value in bucket_map.items():
        if key in text:
            return value
    if "M6" in text or "150" in text:
        return "M6+(150天以上)"
    if overdue_days is None:
        return raw_bucket
    if overdue_days <= 0:
        return "M0(未逾期)"
    if overdue_days <= 30:
        return "M1(1-30天)"
    if overdue_days <= 60:
        return "M2(31-60天)"
    if overdue_days <= 90:
        return "M3(61-90天)"
    if overdue_days <= 120:
        return "M4(91-120天)"
    if overdue_days <= 150:
        return "M5(121-150天)"
    return "M6+(150天以上)"


def _normalize_recovered_status(value: Any) -> Optional[str]:
    text = _parse_text(value, max_length=64)
    if text is None:
        return None
    lowered = text.lower()
    if "入库" in text or "在库" in text:
        return "已入库"
    if "未" in text and ("收回" in text or "拖回" in text or "找回" in text):
        return "未收回"
    if "已" in text and ("收回" in text or "拖回" in text or "扣车" in text or "收车" in text):
        return "已收回未入库"
    if lowered in {"true", "yes", "y", "1"}:
        return "已收回未入库"
    if lowered in {"false", "no", "n", "0"}:
        return "未收回"
    return text[:64]


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


def parse_customer_import(filename: str, content: bytes) -> ParsedImport:
    df = _read_dataframe(filename, content)
    if df.empty:
        return ParsedImport([], 0, 0, 0, {}, [])
    detected_columns, unmapped_columns = detect_columns(list(df.columns))

    rows: list[dict] = []
    for index, record in df.iterrows():
        row_number = int(index) + 2
        raw = {str(col).strip(): _clean_cell(record[col]) for col in df.columns}
        normalized: dict[str, Any] = {}
        errors: list[dict[str, str]] = []

        for field in CANONICAL_FIELDS:
            if field in MONEY_FIELDS or field in INTEGER_FIELDS:
                value, err = _parse_number(_extract(raw, detected_columns, field), field)
                if err:
                    errors.append({"field": field, "message": err})
                normalized[field] = value
            elif field == "recovered_status":
                normalized[field] = _normalize_recovered_status(
                    _extract(raw, detected_columns, field)
                )
            else:
                normalized[field] = _parse_text(
                    _extract(raw, detected_columns, field),
                    max_length=255,
                )

        derived_province, derived_city = _derive_region(normalized.get("location"))
        normalized["province"] = normalized.get("province") or derived_province
        normalized["city"] = normalized.get("city") or derived_city
        normalized["overdue_bucket"] = _normalize_overdue_bucket(
            normalized.get("overdue_bucket"),
            normalized.get("overdue_days"),
        )
        normalized.pop("location", None)

        has_identity = any(
            normalized.get(key)
            for key in (
                "asset_identifier",
                "contract_number",
                "vin",
                "license_plate",
            )
        )
        has_descriptive_identity = normalized.get("debtor_name") and normalized.get(
            "car_description"
        )
        if not has_identity and not has_descriptive_identity:
            errors.append(
                {
                    "field": "asset_identifier",
                    "message": "缺少资产编号/合同号/VIN/车牌，且没有客户+车辆组合",
                }
            )

        rows.append(
            {
                "row_number": row_number,
                "row_status": "error" if errors else "valid",
                "asset_identifier": normalized.get("asset_identifier"),
                "contract_number": normalized.get("contract_number"),
                "debtor_name": normalized.get("debtor_name"),
                "car_description": normalized.get("car_description"),
                "vin": normalized.get("vin"),
                "license_plate": normalized.get("license_plate"),
                "province": normalized.get("province"),
                "city": normalized.get("city"),
                "overdue_bucket": normalized.get("overdue_bucket"),
                "overdue_days": normalized.get("overdue_days"),
                "overdue_amount": normalized.get("overdue_amount"),
                "loan_principal": normalized.get("loan_principal"),
                "vehicle_value": normalized.get("vehicle_value"),
                "recovered_status": normalized.get("recovered_status"),
                "gps_last_seen": normalized.get("gps_last_seen"),
                "errors_json": _json_dumps(errors) if errors else None,
                "raw_json": _json_dumps(raw),
                "normalized_json": _json_dumps(normalized),
            }
        )

    success_rows = sum(1 for row in rows if row["row_status"] == "valid")
    error_rows = len(rows) - success_rows
    return ParsedImport(
        rows=rows,
        total_rows=len(rows),
        success_rows=success_rows,
        error_rows=error_rows,
        detected_columns=detected_columns,
        unmapped_columns=unmapped_columns,
    )


def create_import_batch(
    session: Session,
    *,
    tenant_id: int,
    created_by: Optional[int],
    filename: str,
    source_system: Optional[str],
    import_type: str,
    storage_key: Optional[str],
    content: bytes,
) -> tuple[DataImportBatch, list[DataImportRow], ParsedImport]:
    parsed = parse_customer_import(filename, content)
    status = "failed" if parsed.total_rows > 0 and parsed.success_rows == 0 else "parsed"
    if parsed.total_rows == 0:
        status = "empty"
    if import_type == "asset_ledger" and status == "parsed":
        data_import_repo.archive_active_batches(
            session,
            tenant_id=tenant_id,
            import_type=import_type,
        )
        status = "active"

    batch = data_import_repo.create_batch(
        session,
        tenant_id=tenant_id,
        created_by=created_by,
        import_type=import_type,
        filename=filename,
        source_system=source_system,
        storage_key=storage_key,
        status=status,
        total_rows=parsed.total_rows,
        success_rows=parsed.success_rows,
        error_rows=parsed.error_rows,
    )
    rows = data_import_repo.create_rows(
        session,
        batch_id=batch.id,
        rows=parsed.rows,
    )
    return batch, rows, parsed


def serialize_batch(row: DataImportBatch) -> DataImportBatchOut:
    return DataImportBatchOut(
        id=row.id,
        tenant_id=row.tenant_id,
        created_by=row.created_by,
        import_type=row.import_type,
        filename=row.filename,
        source_system=row.source_system,
        storage_key=row.storage_key,
        status=row.status,
        total_rows=row.total_rows,
        success_rows=row.success_rows,
        error_rows=row.error_rows,
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


def serialize_row(row: DataImportRow) -> DataImportRowOut:
    errors = [
        DataImportError(**item)
        for item in _json_loads(row.errors_json, [])
        if isinstance(item, dict)
    ]
    return DataImportRowOut(
        id=row.id,
        batch_id=row.batch_id,
        row_number=row.row_number,
        row_status=row.row_status,
        asset_identifier=row.asset_identifier,
        contract_number=row.contract_number,
        debtor_name=row.debtor_name,
        car_description=row.car_description,
        vin=row.vin,
        license_plate=row.license_plate,
        province=row.province,
        city=row.city,
        overdue_bucket=row.overdue_bucket,
        overdue_days=row.overdue_days,
        overdue_amount=row.overdue_amount,
        loan_principal=row.loan_principal,
        vehicle_value=row.vehicle_value,
        recovered_status=row.recovered_status,
        gps_last_seen=row.gps_last_seen,
        errors=errors,
        raw=_json_loads(row.raw_json, {}),
        normalized=_json_loads(row.normalized_json, {}),
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


def build_upload_result(
    batch: DataImportBatch,
    rows: list[DataImportRow],
    parsed: ParsedImport,
) -> DataImportUploadResult:
    return DataImportUploadResult(
        batch=serialize_batch(batch),
        rows_preview=[serialize_row(row) for row in rows[:20]],
        detected_columns=parsed.detected_columns,
        unmapped_columns=parsed.unmapped_columns,
    )
