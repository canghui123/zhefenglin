"""Closed-loop learning service for disposal decision models."""

from __future__ import annotations

import json
import math
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.decision_model_config import RegionDisposalCoefficient
from db.models.model_feedback import DisposalOutcome, ModelLearningRun
from models.model_feedback import (
    DisposalOutcomeCreate,
    DisposalOutcomeOut,
    ModelFeedbackBatchImportError,
    ModelFeedbackSummary,
    ModelLearningRunOut,
    RegionAdjustmentSuggestion,
    StrategyAdjustmentSuggestion,
)
from repositories import model_feedback_repo


STRATEGY_PATH_ALIASES = {
    "auction": "retail_auction",
    "拍卖": "retail_auction",
    "拍卖处置": "retail_auction",
    "竞拍": "retail_auction",
    "竞拍处置": "retail_auction",
    "上架竞拍": "retail_auction",
    "立即上架竞拍": "retail_auction",
    "retail_auction": "retail_auction",
    "vehicle_transfer": "retail_auction",
    "bulk_clearance": "retail_auction",
    "towing": "collection",
    "拖车": "collection",
    "拖车处置": "collection",
    "收车": "collection",
    "收车处置": "collection",
    "继续等待赎车/收车": "collection",
    "collection": "collection",
    "redeem_wait": "collection",
    "litigation": "litigation",
    "诉讼": "litigation",
    "常规诉讼": "litigation",
    "lawsuit": "litigation",
    "special_procedure": "special_procedure",
    "特别程序": "special_procedure",
    "担保物权特别程序": "special_procedure",
    "实现担保物权特别程序": "special_procedure",
    "secured_property": "special_procedure",
    "restructure": "restructure",
    "重组": "restructure",
    "和解": "restructure",
    "分期重组": "restructure",
    "重组还款": "restructure",
    "分期重组/和解": "restructure",
    "settlement": "restructure",
}

STRATEGY_NAMES = {
    "collection": "继续等待赎车/收车",
    "litigation": "常规诉讼",
    "retail_auction": "立即上架竞拍",
    "special_procedure": "实现担保物权特别程序",
    "restructure": "分期重组/和解",
}

SUPPORTED_FEEDBACK_EXTENSIONS = {".xlsx", ".xls", ".csv"}

FEEDBACK_FIELD_ALIASES: dict[str, list[str]] = {
    "asset_identifier": [
        "资产/VIN/合同标识",
        "资产标识",
        "资产编号",
        "资产ID",
        "案件编号",
        "账户编号",
        "合同编号",
        "合同号",
        "VIN",
        "车架号",
        "车辆识别代码",
        "asset_identifier",
    ],
    "strategy_path": [
        "实际路径",
        "处置路径",
        "处置方式",
        "实际处置方式",
        "策略路径",
        "路径",
        "strategy_path",
    ],
    "source_type": ["来源类型", "来源", "source_type"],
    "source_id": ["来源ID", "来源编号", "source_id"],
    "province": ["省份", "省", "资产省份"],
    "city": ["城市", "市", "资产城市"],
    "predicted_recovery_amount": [
        "预测回款",
        "预测回款金额",
        "预计回款",
        "模型预测回款",
        "predicted_recovery_amount",
    ],
    "actual_recovery_amount": [
        "实际回款",
        "实际回款金额",
        "真实回款",
        "处置回款",
        "actual_recovery_amount",
    ],
    "predicted_cycle_days": [
        "预测周期",
        "预测周期(天)",
        "预计周期",
        "模型预测周期",
        "predicted_cycle_days",
    ],
    "actual_cycle_days": [
        "实际周期",
        "实际周期(天)",
        "真实周期",
        "处置周期",
        "actual_cycle_days",
    ],
    "predicted_success_probability": [
        "预测成功率",
        "模型预测成功率",
        "预计成功率",
        "成功率预测",
        "predicted_success_probability",
    ],
    "outcome_status": [
        "实际结果",
        "处置结果",
        "结果状态",
        "回款结果",
        "outcome_status",
    ],
    "notes": ["复盘备注", "备注", "说明", "notes"],
}

FEEDBACK_REQUIRED_FIELDS = {
    "asset_identifier": "资产/VIN/合同标识",
    "strategy_path": "实际路径",
    "predicted_recovery_amount": "预测回款",
    "actual_recovery_amount": "实际回款",
    "predicted_cycle_days": "预测周期",
    "actual_cycle_days": "实际周期",
    "predicted_success_probability": "预测成功率",
    "outcome_status": "实际结果",
}


@dataclass
class ParsedFeedbackImport:
    rows: list[DisposalOutcomeCreate]
    total_rows: int
    error_rows: int
    errors: list[ModelFeedbackBatchImportError]
    detected_columns: dict[str, str]
    unmapped_columns: list[str]


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return min(max(value, min_value), max_value)


def _json_loads(value: Optional[str]) -> dict:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def _json_dumps(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _clean_import_cell(value: Any) -> Optional[Any]:
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


def _parse_import_text(value: Any, *, max_length: int = 255) -> Optional[str]:
    cleaned = _clean_import_cell(value)
    if cleaned is None:
        return None
    text = str(cleaned).strip()
    return text[:max_length] if text else None


def _parse_import_number(value: Any, *, integer: bool = False) -> tuple[Optional[float], Optional[str]]:
    cleaned = _clean_import_cell(value)
    if cleaned is None:
        return None, None
    if isinstance(cleaned, (int, float)):
        number = float(cleaned)
    else:
        text = str(cleaned).strip()
        multiplier = 1.0
        if text.lower().endswith("w") or text.endswith("万"):
            multiplier = 10000.0
            text = text[:-1]
        text = (
            text.replace(",", "")
            .replace("，", "")
            .replace("¥", "")
            .replace("￥", "")
            .replace("元", "")
            .replace("天", "")
            .replace("%", "")
            .replace("％", "")
            .strip()
        )
        try:
            number = float(text) * multiplier
        except ValueError:
            return None, "无法解析为数字"
    if number < 0:
        return None, "不能小于0"
    if integer:
        if number < 1:
            return None, "必须大于等于1"
        return int(round(number)), None
    return number, None


def _parse_import_rate(value: Any) -> tuple[Optional[float], Optional[str]]:
    cleaned = _clean_import_cell(value)
    if cleaned is None:
        return None, None
    text = str(cleaned).strip()
    number, error = _parse_import_number(cleaned)
    if error:
        return None, error
    if number is None:
        return None, None
    if "%" in text or number > 1:
        number = number / 100
    if number < 0 or number > 1:
        return None, "必须在0到1之间，或填写0%-100%"
    return number, None


def _normalize_import_header(value: Any) -> str:
    text = str(value).strip().lower()
    return re.sub(r"[\s_\-/:：()（）]+", "", text)


def _detect_feedback_columns(columns: list[Any]) -> tuple[dict[str, str], list[str]]:
    alias_to_field: dict[str, str] = {}
    for field, aliases in FEEDBACK_FIELD_ALIASES.items():
        for alias in aliases + [field]:
            alias_to_field[_normalize_import_header(alias)] = field

    detected: dict[str, str] = {}
    used: set[str] = set()
    for col in columns:
        original = str(col).strip()
        field = alias_to_field.get(_normalize_import_header(col))
        if field and field not in detected:
            detected[field] = original
            used.add(original)
    unmapped = [str(col).strip() for col in columns if str(col).strip() not in used]
    return detected, unmapped


def _extract_feedback_value(raw: dict[str, Any], detected: dict[str, str], field: str) -> Any:
    column = detected.get(field)
    if not column:
        return None
    return raw.get(column)


def _read_feedback_dataframe(filename: str, content: bytes) -> pd.DataFrame:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in SUPPORTED_FEEDBACK_EXTENSIONS:
        raise ValueError("仅支持 .xlsx、.xls 或 .csv 文件")
    if ext == ".csv":
        for encoding in ("utf-8-sig", "gbk", "gb18030"):
            try:
                return pd.read_csv(BytesIO(content), encoding=encoding)
            except UnicodeDecodeError:
                continue
        return pd.read_csv(BytesIO(content))
    return pd.read_excel(BytesIO(content))


def _normalize_strategy_path(value: Optional[str]) -> str:
    normalized = (value or "").strip().lower()
    return STRATEGY_PATH_ALIASES.get(normalized, normalized or "unknown")


def _normalize_outcome_status(value: Any) -> Optional[str]:
    text = _parse_import_text(value, max_length=64)
    if text is None:
        return None
    normalized = text.strip().lower()
    if normalized in {"success", "succeeded", "成功", "已成功", "已回款", "已结清", "已处置"}:
        return "success"
    if normalized in {"partial", "partially_success", "部分成功", "部分", "部分回款", "部分处置"}:
        return "partial"
    if normalized in {"failed", "failure", "失败", "未成功", "未回款", "未处置", "流拍"}:
        return "failed"
    return None


def _strategy_name(value: str) -> str:
    return STRATEGY_NAMES.get(value, value)


def _success_score(status: str) -> float:
    if status == "success":
        return 1.0
    if status == "partial":
        return 0.5
    return 0.0


def _strategy_adjustments_from_payload(payload: dict) -> list[StrategyAdjustmentSuggestion]:
    suggestions: list[StrategyAdjustmentSuggestion] = []
    for item in payload.get("strategies", []):
        try:
            suggestions.append(StrategyAdjustmentSuggestion(**item))
        except (TypeError, ValueError):
            continue
    return suggestions


def serialize_disposal_outcome(row: DisposalOutcome) -> DisposalOutcomeOut:
    return DisposalOutcomeOut(
        id=row.id,
        tenant_id=row.tenant_id,
        created_by=row.created_by,
        asset_identifier=row.asset_identifier,
        strategy_path=row.strategy_path,
        source_type=row.source_type,
        source_id=row.source_id,
        province=row.province,
        city=row.city,
        predicted_recovery_amount=row.predicted_recovery_amount,
        actual_recovery_amount=row.actual_recovery_amount,
        predicted_cycle_days=row.predicted_cycle_days,
        actual_cycle_days=row.actual_cycle_days,
        predicted_success_probability=row.predicted_success_probability,
        outcome_status=row.outcome_status,
        notes=row.notes,
        metadata=_json_loads(row.metadata_json),
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


def serialize_learning_run(row: ModelLearningRun) -> ModelLearningRunOut:
    payload = _json_loads(row.region_adjustments_json)
    return ModelLearningRunOut(
        id=row.id,
        tenant_id=row.tenant_id,
        created_by=row.created_by,
        sample_count=row.sample_count,
        recovery_bias_ratio=row.recovery_bias_ratio,
        cycle_bias_ratio=row.cycle_bias_ratio,
        actual_success_rate=row.actual_success_rate,
        avg_predicted_success_probability=row.avg_predicted_success_probability,
        suggested_success_adjustment=row.suggested_success_adjustment,
        region_adjustments=[
            RegionAdjustmentSuggestion(**item)
            for item in payload.get("regions", [])
        ],
        strategy_adjustments=_strategy_adjustments_from_payload(payload),
        applied=row.applied,
        success_adjustment_applied=row.success_adjustment_applied,
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


def record_disposal_outcome(
    session: Session,
    *,
    tenant_id: int,
    created_by: Optional[int],
    req: DisposalOutcomeCreate,
) -> DisposalOutcome:
    return model_feedback_repo.create_disposal_outcome(
        session,
        tenant_id=tenant_id,
        created_by=created_by,
        source_type=req.source_type,
        source_id=req.source_id,
        asset_identifier=req.asset_identifier,
        strategy_path=req.strategy_path,
        province=req.province,
        city=req.city,
        predicted_recovery_amount=req.predicted_recovery_amount,
        actual_recovery_amount=req.actual_recovery_amount,
        predicted_cycle_days=req.predicted_cycle_days,
        actual_cycle_days=req.actual_cycle_days,
        predicted_success_probability=req.predicted_success_probability,
        outcome_status=req.outcome_status,
        notes=req.notes,
        metadata_json=_json_dumps(req.metadata),
    )


def _add_import_error(
    errors: list[ModelFeedbackBatchImportError],
    *,
    row_number: int,
    field: str,
    message: str,
) -> None:
    errors.append(
        ModelFeedbackBatchImportError(
            row_number=row_number,
            field=field,
            message=message,
        )
    )


def parse_feedback_batch_import(filename: str, content: bytes) -> ParsedFeedbackImport:
    df = _read_feedback_dataframe(filename, content)
    if df.empty:
        return ParsedFeedbackImport(
            rows=[],
            total_rows=0,
            error_rows=0,
            errors=[],
            detected_columns={},
            unmapped_columns=[],
        )

    detected, unmapped = _detect_feedback_columns(list(df.columns))
    valid_rows: list[DisposalOutcomeCreate] = []
    errors: list[ModelFeedbackBatchImportError] = []
    error_row_numbers: set[int] = set()

    for index, record in df.iterrows():
        row_number = int(index) + 2
        row_errors: list[ModelFeedbackBatchImportError] = []
        raw = {str(col).strip(): _clean_import_cell(record[col]) for col in df.columns}

        asset_identifier = _parse_import_text(
            _extract_feedback_value(raw, detected, "asset_identifier"),
            max_length=120,
        )
        strategy_raw = _parse_import_text(
            _extract_feedback_value(raw, detected, "strategy_path"),
            max_length=64,
        )
        strategy_path = _normalize_strategy_path(strategy_raw)
        source_type = _parse_import_text(
            _extract_feedback_value(raw, detected, "source_type"),
            max_length=64,
        ) or "batch_feedback_upload"
        source_id = _parse_import_text(
            _extract_feedback_value(raw, detected, "source_id"),
            max_length=100,
        ) or f"{filename}:row:{row_number}"[:100]
        province = _parse_import_text(
            _extract_feedback_value(raw, detected, "province"),
            max_length=64,
        )
        city = _parse_import_text(
            _extract_feedback_value(raw, detected, "city"),
            max_length=64,
        )
        notes = _parse_import_text(
            _extract_feedback_value(raw, detected, "notes"),
            max_length=1000,
        )

        predicted_recovery, predicted_recovery_error = _parse_import_number(
            _extract_feedback_value(raw, detected, "predicted_recovery_amount")
        )
        actual_recovery, actual_recovery_error = _parse_import_number(
            _extract_feedback_value(raw, detected, "actual_recovery_amount")
        )
        predicted_days, predicted_days_error = _parse_import_number(
            _extract_feedback_value(raw, detected, "predicted_cycle_days"),
            integer=True,
        )
        actual_days, actual_days_error = _parse_import_number(
            _extract_feedback_value(raw, detected, "actual_cycle_days"),
            integer=True,
        )
        predicted_success, predicted_success_error = _parse_import_rate(
            _extract_feedback_value(raw, detected, "predicted_success_probability")
        )
        outcome_status = _normalize_outcome_status(
            _extract_feedback_value(raw, detected, "outcome_status")
        )

        required_values = {
            "asset_identifier": asset_identifier,
            "strategy_path": strategy_raw,
            "predicted_recovery_amount": predicted_recovery,
            "actual_recovery_amount": actual_recovery,
            "predicted_cycle_days": predicted_days,
            "actual_cycle_days": actual_days,
            "predicted_success_probability": predicted_success,
            "outcome_status": outcome_status,
        }
        for field, label in FEEDBACK_REQUIRED_FIELDS.items():
            if required_values.get(field) is None:
                _add_import_error(
                    row_errors,
                    row_number=row_number,
                    field=field,
                    message=f"缺少{label}",
                )

        for field, error in {
            "predicted_recovery_amount": predicted_recovery_error,
            "actual_recovery_amount": actual_recovery_error,
            "predicted_cycle_days": predicted_days_error,
            "actual_cycle_days": actual_days_error,
            "predicted_success_probability": predicted_success_error,
        }.items():
            if error:
                _add_import_error(
                    row_errors,
                    row_number=row_number,
                    field=field,
                    message=error,
                )

        if strategy_raw and strategy_path == "unknown":
            _add_import_error(
                row_errors,
                row_number=row_number,
                field="strategy_path",
                message="无法识别处置路径",
            )
        if _extract_feedback_value(raw, detected, "outcome_status") is not None and outcome_status is None:
            _add_import_error(
                row_errors,
                row_number=row_number,
                field="outcome_status",
                message="实际结果只能是成功、部分成功或失败",
            )

        if row_errors:
            errors.extend(row_errors)
            error_row_numbers.add(row_number)
            continue

        valid_rows.append(
            DisposalOutcomeCreate(
                asset_identifier=asset_identifier or "",
                strategy_path=strategy_path,
                source_type=source_type,
                source_id=source_id,
                province=province,
                city=city,
                predicted_recovery_amount=float(predicted_recovery or 0),
                actual_recovery_amount=float(actual_recovery or 0),
                predicted_cycle_days=int(predicted_days or 1),
                actual_cycle_days=int(actual_days or 1),
                predicted_success_probability=float(predicted_success or 0),
                outcome_status=outcome_status or "failed",
                notes=notes,
                metadata={
                    "import_filename": filename,
                    "import_row_number": row_number,
                    "raw": raw,
                    "detected_columns": detected,
                },
            )
        )

    return ParsedFeedbackImport(
        rows=valid_rows,
        total_rows=len(df),
        error_rows=len(error_row_numbers),
        errors=errors,
        detected_columns=detected,
        unmapped_columns=unmapped,
    )


def import_feedback_batch_and_run_learning(
    session: Session,
    *,
    tenant_id: int,
    created_by: Optional[int],
    filename: str,
    content: bytes,
    apply_region_adjustments: bool = False,
    apply_success_adjustment: bool = False,
) -> tuple[ParsedFeedbackImport, list[DisposalOutcome], Optional[ModelLearningRun]]:
    parsed = parse_feedback_batch_import(filename, content)
    created_rows = [
        record_disposal_outcome(
            session,
            tenant_id=tenant_id,
            created_by=created_by,
            req=req,
        )
        for req in parsed.rows
    ]
    learning_run = None
    if created_rows:
        learning_run = run_learning_cycle(
            session,
            tenant_id=tenant_id,
            created_by=created_by,
            apply_region_adjustments=apply_region_adjustments,
            apply_success_adjustment=apply_success_adjustment,
        )
    return parsed, created_rows, learning_run


def _bias_ratio(actual: float, predicted: float) -> float:
    if predicted <= 0:
        return 0.0
    return round((actual / predicted) - 1.0, 4)


def _compute_region_adjustments(outcomes: list[DisposalOutcome]) -> list[RegionAdjustmentSuggestion]:
    grouped: dict[tuple[str, str], list[DisposalOutcome]] = defaultdict(list)
    for row in outcomes:
        key = ((row.province or "全国").strip(), (row.city or "").strip())
        grouped[key].append(row)

    suggestions: list[RegionAdjustmentSuggestion] = []
    for (province, city), rows in grouped.items():
        if not rows:
            continue
        predicted_recovery = sum(row.predicted_recovery_amount for row in rows)
        actual_recovery = sum(row.actual_recovery_amount for row in rows)
        predicted_days = sum(row.predicted_cycle_days for row in rows) / len(rows)
        actual_days = sum(row.actual_cycle_days for row in rows) / len(rows)
        recovery_bias = _bias_ratio(actual_recovery, predicted_recovery)
        cycle_bias = _bias_ratio(actual_days, predicted_days)
        speed_multiplier = _clamp(1 / max(actual_days / max(predicted_days, 1), 0.1), 0.75, 1.25)
        legal_multiplier = _clamp(speed_multiplier, 0.85, 1.15)
        suggestions.append(
            RegionAdjustmentSuggestion(
                province=province,
                city=city or None,
                sample_count=len(rows),
                recovery_bias_ratio=round(recovery_bias, 4),
                cycle_bias_ratio=round(cycle_bias, 4),
                liquidity_speed_multiplier=round(speed_multiplier, 4),
                legal_efficiency_multiplier=round(legal_multiplier, 4),
            )
        )
    return sorted(suggestions, key=lambda item: item.sample_count, reverse=True)


def _compute_strategy_adjustments(outcomes: list[DisposalOutcome]) -> list[StrategyAdjustmentSuggestion]:
    grouped: dict[str, list[DisposalOutcome]] = defaultdict(list)
    for row in outcomes:
        grouped[_normalize_strategy_path(row.strategy_path)].append(row)

    suggestions: list[StrategyAdjustmentSuggestion] = []
    for strategy_path, rows in grouped.items():
        if not rows:
            continue
        actual_success_rate = sum(_success_score(row.outcome_status) for row in rows) / len(rows)
        avg_predicted_success = sum(row.predicted_success_probability for row in rows) / len(rows)
        suggested_adjustment = _clamp(
            actual_success_rate - avg_predicted_success,
            -0.15,
            0.15,
        )
        suggestions.append(
            StrategyAdjustmentSuggestion(
                strategy_path=strategy_path,
                strategy_name=_strategy_name(strategy_path),
                sample_count=len(rows),
                actual_success_rate=round(actual_success_rate, 4),
                avg_predicted_success_probability=round(avg_predicted_success, 4),
                suggested_success_adjustment=round(suggested_adjustment, 4),
            )
        )

    return sorted(suggestions, key=lambda item: item.sample_count, reverse=True)


def compute_feedback_summary(
    session: Session,
    *,
    tenant_id: int,
) -> ModelFeedbackSummary:
    active_success_run = model_feedback_repo.get_latest_applied_success_adjustment_run(
        session,
        tenant_id=tenant_id,
    )
    active_success_adjustment = (
        _clamp(active_success_run.suggested_success_adjustment, -0.15, 0.15)
        if active_success_run is not None
        else 0.0
    )
    active_strategy_adjustments = (
        _strategy_adjustments_from_payload(_json_loads(active_success_run.region_adjustments_json))
        if active_success_run is not None
        else []
    )
    outcomes = model_feedback_repo.list_all_outcomes_for_learning(
        session,
        tenant_id=tenant_id,
    )
    sample_count = len(outcomes)
    if sample_count == 0:
        return ModelFeedbackSummary(
            sample_count=0,
            recovery_bias_ratio=0.0,
            cycle_bias_ratio=0.0,
            actual_success_rate=0.0,
            avg_predicted_success_probability=0.0,
            suggested_success_adjustment=0.0,
            active_success_adjustment=active_success_adjustment,
            active_success_adjustment_run_id=active_success_run.id if active_success_run else None,
            region_adjustments=[],
            strategy_adjustments=[],
            active_strategy_adjustments=active_strategy_adjustments,
        )

    predicted_recovery = sum(row.predicted_recovery_amount for row in outcomes)
    actual_recovery = sum(row.actual_recovery_amount for row in outcomes)
    predicted_days = sum(row.predicted_cycle_days for row in outcomes) / sample_count
    actual_days = sum(row.actual_cycle_days for row in outcomes) / sample_count
    actual_success_rate = sum(1 for row in outcomes if row.outcome_status == "success") / sample_count
    avg_predicted_success = (
        sum(row.predicted_success_probability for row in outcomes) / sample_count
    )
    suggested_success_adjustment = _clamp(actual_success_rate - avg_predicted_success, -0.15, 0.15)

    return ModelFeedbackSummary(
        sample_count=sample_count,
        recovery_bias_ratio=_bias_ratio(actual_recovery, predicted_recovery),
        cycle_bias_ratio=_bias_ratio(actual_days, predicted_days),
        actual_success_rate=round(actual_success_rate, 4),
        avg_predicted_success_probability=round(avg_predicted_success, 4),
        suggested_success_adjustment=round(suggested_success_adjustment, 4),
        active_success_adjustment=round(active_success_adjustment, 4),
        active_success_adjustment_run_id=active_success_run.id if active_success_run else None,
        region_adjustments=_compute_region_adjustments(outcomes),
        strategy_adjustments=_compute_strategy_adjustments(outcomes),
        active_strategy_adjustments=active_strategy_adjustments,
    )


def _find_region_row(
    session: Session,
    *,
    province: Optional[str],
    city: Optional[str],
) -> Optional[RegionDisposalCoefficient]:
    province = (province or "").strip()
    city = (city or "").strip()
    if not province:
        return None
    if city:
        row = session.scalars(
            select(RegionDisposalCoefficient)
            .where(RegionDisposalCoefficient.province == province)
            .where(RegionDisposalCoefficient.city == city)
            .where(RegionDisposalCoefficient.is_active.is_(True))
            .limit(1)
        ).first()
        if row is not None:
            return row
    return session.scalars(
        select(RegionDisposalCoefficient)
        .where(RegionDisposalCoefficient.province == province)
        .where(RegionDisposalCoefficient.city.is_(None))
        .where(RegionDisposalCoefficient.is_active.is_(True))
        .limit(1)
    ).first()


def _apply_region_adjustments(
    session: Session,
    suggestions: list[RegionAdjustmentSuggestion],
) -> None:
    for suggestion in suggestions:
        row = _find_region_row(
            session,
            province=suggestion.province,
            city=suggestion.city,
        )
        if row is None:
            continue
        row.liquidity_speed_factor = round(
            _clamp(row.liquidity_speed_factor * suggestion.liquidity_speed_multiplier, 0.60, 1.60),
            4,
        )
        row.legal_efficiency_factor = round(
            _clamp(row.legal_efficiency_factor * suggestion.legal_efficiency_multiplier, 0.60, 1.60),
            4,
        )
    session.flush()


def run_learning_cycle(
    session: Session,
    *,
    tenant_id: int,
    created_by: Optional[int],
    apply_region_adjustments: bool = False,
    apply_success_adjustment: bool = False,
) -> ModelLearningRun:
    summary = compute_feedback_summary(session, tenant_id=tenant_id)
    if apply_region_adjustments and summary.region_adjustments:
        _apply_region_adjustments(session, summary.region_adjustments)

    return model_feedback_repo.create_learning_run(
        session,
        tenant_id=tenant_id,
        created_by=created_by,
        sample_count=summary.sample_count,
        recovery_bias_ratio=summary.recovery_bias_ratio,
        cycle_bias_ratio=summary.cycle_bias_ratio,
        actual_success_rate=summary.actual_success_rate,
        avg_predicted_success_probability=summary.avg_predicted_success_probability,
        suggested_success_adjustment=summary.suggested_success_adjustment,
        region_adjustments_json=_json_dumps(
            {
                "regions": [item.model_dump() for item in summary.region_adjustments],
                "strategies": [item.model_dump() for item in summary.strategy_adjustments],
            }
        ),
        applied=apply_region_adjustments or apply_success_adjustment,
        success_adjustment_applied=apply_success_adjustment,
    )


def get_applied_success_adjustment(
    session: Optional[Session],
    *,
    tenant_id: Optional[int],
    strategy_path: Optional[str] = None,
) -> float:
    if session is None or tenant_id is None:
        return 0.0
    run = model_feedback_repo.get_latest_applied_success_adjustment_run(
        session,
        tenant_id=tenant_id,
    )
    if run is None:
        return 0.0

    if strategy_path:
        payload = _json_loads(run.region_adjustments_json)
        strategies = _strategy_adjustments_from_payload(payload)
        if strategies:
            normalized_path = _normalize_strategy_path(strategy_path)
            for item in strategies:
                if _normalize_strategy_path(item.strategy_path) == normalized_path:
                    return _clamp(item.suggested_success_adjustment, -0.15, 0.15)
            return 0.0

    return _clamp(run.suggested_success_adjustment, -0.15, 0.15)
