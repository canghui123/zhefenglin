"""Repository for portfolio-related tables.

The current `api/portfolio.py` still serves mock data, so this module only
exposes the bare CRUD primitives that Task 6+ tasks will wire up later.
"""
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
) -> PortfolioSnapshot:
    snap = PortfolioSnapshot(
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


def list_segments(session: Session, org_id: str) -> List[AssetSegment]:
    stmt = select(AssetSegment).where(AssetSegment.org_id == org_id)
    return list(session.scalars(stmt).all())


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
