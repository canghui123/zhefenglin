"""Repository helpers for model feedback loop."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.model_feedback import DisposalOutcome, ModelLearningRun


def create_disposal_outcome(
    session: Session,
    *,
    tenant_id: int,
    created_by: Optional[int],
    source_type: Optional[str],
    source_id: Optional[str],
    asset_identifier: str,
    strategy_path: str,
    province: Optional[str],
    city: Optional[str],
    predicted_recovery_amount: float,
    actual_recovery_amount: float,
    predicted_cycle_days: int,
    actual_cycle_days: int,
    predicted_success_probability: float,
    outcome_status: str,
    notes: Optional[str],
    metadata_json: str,
) -> DisposalOutcome:
    row = DisposalOutcome(
        tenant_id=tenant_id,
        created_by=created_by,
        source_type=source_type,
        source_id=source_id,
        asset_identifier=asset_identifier,
        strategy_path=strategy_path,
        province=province,
        city=city,
        predicted_recovery_amount=predicted_recovery_amount,
        actual_recovery_amount=actual_recovery_amount,
        predicted_cycle_days=predicted_cycle_days,
        actual_cycle_days=actual_cycle_days,
        predicted_success_probability=predicted_success_probability,
        outcome_status=outcome_status,
        notes=notes,
        metadata_json=metadata_json,
    )
    session.add(row)
    session.flush()
    return row


def list_disposal_outcomes(
    session: Session,
    *,
    tenant_id: int,
    limit: int = 100,
) -> list[DisposalOutcome]:
    stmt = (
        select(DisposalOutcome)
        .where(DisposalOutcome.tenant_id == tenant_id)
        .order_by(DisposalOutcome.created_at.desc(), DisposalOutcome.id.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def list_all_outcomes_for_learning(
    session: Session,
    *,
    tenant_id: int,
) -> list[DisposalOutcome]:
    stmt = (
        select(DisposalOutcome)
        .where(DisposalOutcome.tenant_id == tenant_id)
        .order_by(DisposalOutcome.created_at.asc(), DisposalOutcome.id.asc())
    )
    return list(session.scalars(stmt).all())


def create_learning_run(
    session: Session,
    *,
    tenant_id: int,
    created_by: Optional[int],
    sample_count: int,
    recovery_bias_ratio: float,
    cycle_bias_ratio: float,
    actual_success_rate: float,
    avg_predicted_success_probability: float,
    suggested_success_adjustment: float,
    region_adjustments_json: str,
    applied: bool,
    success_adjustment_applied: bool = False,
) -> ModelLearningRun:
    row = ModelLearningRun(
        tenant_id=tenant_id,
        created_by=created_by,
        sample_count=sample_count,
        recovery_bias_ratio=recovery_bias_ratio,
        cycle_bias_ratio=cycle_bias_ratio,
        actual_success_rate=actual_success_rate,
        avg_predicted_success_probability=avg_predicted_success_probability,
        suggested_success_adjustment=suggested_success_adjustment,
        region_adjustments_json=region_adjustments_json,
        applied=applied,
        success_adjustment_applied=success_adjustment_applied,
    )
    session.add(row)
    session.flush()
    return row


def list_learning_runs(
    session: Session,
    *,
    tenant_id: int,
    limit: int = 20,
) -> list[ModelLearningRun]:
    stmt = (
        select(ModelLearningRun)
        .where(ModelLearningRun.tenant_id == tenant_id)
        .order_by(ModelLearningRun.created_at.desc(), ModelLearningRun.id.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def get_latest_applied_success_adjustment(
    session: Session,
    *,
    tenant_id: int,
) -> float:
    row = session.scalars(
        select(ModelLearningRun)
        .where(ModelLearningRun.tenant_id == tenant_id)
        .where(ModelLearningRun.success_adjustment_applied.is_(True))
        .order_by(ModelLearningRun.created_at.desc(), ModelLearningRun.id.desc())
        .limit(1)
    ).first()
    return row.suggested_success_adjustment if row is not None else 0.0
