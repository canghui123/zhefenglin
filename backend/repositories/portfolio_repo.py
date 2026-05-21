"""Repository for portfolio-related tables."""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.portfolio import (
    PortfolioSnapshot,
    AssetSegment,
    SegmentMetric,
    StrategyRun,
    ManagementGoal,
    RecommendedAction,
)


def create_snapshot(
    session: Session,
    *,
    org_id: str,
    snapshot_date: str,
    scenario_name: str = "baseline",
    tenant_id: Optional[int] = None,
) -> PortfolioSnapshot:
    snap = PortfolioSnapshot(
        tenant_id=tenant_id,
        org_id=org_id,
        snapshot_date=snapshot_date,
        scenario_name=scenario_name,
    )
    session.add(snap)
    session.flush()
    return snap


def get_snapshot_by_id(
    session: Session, snapshot_id: int
) -> Optional[PortfolioSnapshot]:
    return session.get(PortfolioSnapshot, snapshot_id)


def list_snapshots(session: Session, org_id: str) -> List[PortfolioSnapshot]:
    stmt = (
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.org_id == org_id)
        .order_by(PortfolioSnapshot.created_at.desc())
    )
    return list(session.scalars(stmt).all())


def get_latest_snapshot_for_tenant(
    session: Session,
    tenant_id: int,
) -> Optional[PortfolioSnapshot]:
    stmt = (
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.tenant_id == tenant_id)
        .order_by(PortfolioSnapshot.snapshot_date.desc(), PortfolioSnapshot.created_at.desc(), PortfolioSnapshot.id.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def list_segments(session: Session, org_id: str) -> List[AssetSegment]:
    stmt = select(AssetSegment).where(AssetSegment.org_id == org_id)
    return list(session.scalars(stmt).all())


def list_snapshot_segment_metrics(
    session: Session,
    *,
    snapshot_id: int,
    tenant_id: int,
) -> list[tuple[AssetSegment, SegmentMetric]]:
    stmt = (
        select(AssetSegment, SegmentMetric)
        .join(SegmentMetric, SegmentMetric.segment_id == AssetSegment.id)
        .where(SegmentMetric.snapshot_id == snapshot_id)
        .where(AssetSegment.tenant_id == tenant_id)
        .order_by(AssetSegment.id)
    )
    return list(session.execute(stmt).all())


def build_capacity_segments(
    rows: list[tuple[AssetSegment, SegmentMetric]],
) -> list[dict]:
    segments: list[dict] = []
    for segment, metric in rows:
        if metric.asset_count <= 0:
            continue
        segments.append(
            {
                "segment_name": segment.name,
                "overdue_bucket": segment.overdue_bucket or "其他",
                "recovered_status": segment.recovered_status or "未收回",
                "inventory_bucket": segment.inventory_bucket,
                "asset_count": metric.asset_count,
                "total_ead": metric.total_ead,
                "avg_vehicle_value": metric.avg_vehicle_value,
                "avg_lgd": metric.avg_lgd,
                "avg_recovery_days": metric.avg_recovery_days,
                "expected_loss_amount": metric.expected_loss_amount,
                "expected_loss_rate": metric.expected_loss_rate,
                "cash_30d": metric.expected_cash_30d,
                "cash_90d": metric.expected_cash_90d,
                "cash_180d": metric.expected_cash_180d,
                "recommended_strategy": metric.recommended_strategy,
            }
        )
    return segments


def save_segment_metric(
    session: Session,
    *,
    snapshot_id: int,
    segment_id: int,
    **fields,
) -> SegmentMetric:
    metric = SegmentMetric(snapshot_id=snapshot_id, segment_id=segment_id, **fields)
    session.add(metric)
    session.flush()
    return metric


def save_strategy_run(
    session: Session,
    *,
    snapshot_id: int,
    segment_id: int,
    strategy_type: str,
    **fields,
) -> StrategyRun:
    run = StrategyRun(
        snapshot_id=snapshot_id,
        segment_id=segment_id,
        strategy_type=strategy_type,
        **fields,
    )
    session.add(run)
    session.flush()
    return run


def list_management_goals(
    session: Session, org_id: str
) -> List[ManagementGoal]:
    stmt = (
        select(ManagementGoal)
        .where(ManagementGoal.org_id == org_id)
        .where(ManagementGoal.status == "active")
    )
    return list(session.scalars(stmt).all())


def list_recommendations(
    session: Session, snapshot_id: int
) -> List[RecommendedAction]:
    stmt = (
        select(RecommendedAction)
        .where(RecommendedAction.snapshot_id == snapshot_id)
        .order_by(RecommendedAction.priority)
    )
    return list(session.scalars(stmt).all())
