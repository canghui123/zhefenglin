from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from db.base import Base


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(String, default="default", nullable=False)
    snapshot_date: Mapped[str] = mapped_column(String, nullable=False)
    scenario_name: Mapped[str] = mapped_column(String, default="baseline", nullable=False)
    total_ead: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    total_book_value: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    total_expected_loss: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    total_expected_loss_rate: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    total_expected_cash_30d: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    total_expected_cash_90d: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    total_expected_cash_180d: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    total_provision_impact: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    total_capital_impact: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class AssetSegment(Base):
    __tablename__ = "asset_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(String, default="default", nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    overdue_bucket: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    recovered_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    inventory_bucket: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    legal_completeness: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    vehicle_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    region: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    custom_rules_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class SegmentMetric(Base):
    __tablename__ = "segment_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("portfolio_snapshots.id"), nullable=True
    )
    segment_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("asset_segments.id"), nullable=True
    )
    asset_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_ead: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    avg_vehicle_value: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    avg_lgd: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    avg_recovery_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expected_loss_amount: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    expected_loss_rate: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    expected_cash_30d: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    expected_cash_90d: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    expected_cash_180d: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    recommended_strategy: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class StrategyRun(Base):
    __tablename__ = "strategy_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("portfolio_snapshots.id"), nullable=True
    )
    segment_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("asset_segments.id"), nullable=True
    )
    strategy_type: Mapped[str] = mapped_column(String, nullable=False)
    success_probability: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    expected_recovery_gross: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    towing_cost: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    inventory_cost: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    legal_cost: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    refurbishment_cost: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    channel_fee: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    funding_cost: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    management_cost: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    discount_cost: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    net_recovery_pv: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    expected_loss_amount: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    expected_loss_rate: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    expected_recovery_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    capital_release_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    notes_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class CashflowBucket(Base):
    __tablename__ = "cashflow_buckets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_run_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("strategy_runs.id"), nullable=True
    )
    bucket_day: Mapped[int] = mapped_column(Integer, nullable=False)
    gross_cash_in: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    gross_cash_out: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    net_cash_flow: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    discounted_net_cash_flow: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class ManagementGoal(Base):
    __tablename__ = "management_goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    org_id: Mapped[str] = mapped_column(String, default="default", nullable=False)
    period_type: Mapped[str] = mapped_column(String, default="month", nullable=False)
    role_level: Mapped[str] = mapped_column(String, default="manager", nullable=False)
    goal_name: Mapped[str] = mapped_column(String, nullable=False)
    goal_category: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    target_value: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    target_unit: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    baseline_value: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    confidence_level: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    constraint_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class RecommendedAction(Base):
    __tablename__ = "recommended_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("portfolio_snapshots.id"), nullable=True
    )
    role_level: Mapped[str] = mapped_column(String, nullable=False)
    segment_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    strategy_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    recommendation_title: Mapped[str] = mapped_column(String, nullable=False)
    recommendation_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expected_loss_impact: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    expected_cashflow_impact: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    expected_inventory_impact: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    feasibility_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    realism_score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    resource_need_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approval_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    dependencies_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
