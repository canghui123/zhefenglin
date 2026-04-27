"""Closed-loop learning service for disposal decision models."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.decision_model_config import RegionDisposalCoefficient
from db.models.model_feedback import DisposalOutcome, ModelLearningRun
from models.model_feedback import (
    DisposalOutcomeCreate,
    DisposalOutcomeOut,
    ModelFeedbackSummary,
    ModelLearningRunOut,
    RegionAdjustmentSuggestion,
)
from repositories import model_feedback_repo


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
            for item in _json_loads(row.region_adjustments_json).get("regions", [])
        ],
        applied=row.applied,
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


def compute_feedback_summary(
    session: Session,
    *,
    tenant_id: int,
) -> ModelFeedbackSummary:
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
            region_adjustments=[],
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
        region_adjustments=_compute_region_adjustments(outcomes),
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
            {"regions": [item.model_dump() for item in summary.region_adjustments]}
        ),
        applied=apply_region_adjustments,
    )
