"""Model feedback loop tables."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class DisposalOutcome(Base):
    __tablename__ = "disposal_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    asset_identifier: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    strategy_path: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    province: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    city: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    predicted_recovery_amount: Mapped[float] = mapped_column(Float, nullable=False)
    actual_recovery_amount: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_cycle_days: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_cycle_days: Mapped[int] = mapped_column(Integer, nullable=False)
    predicted_success_probability: Mapped[float] = mapped_column(Float, nullable=False)
    outcome_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        index=True,
    )


class ModelLearningRun(Base):
    __tablename__ = "model_learning_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    recovery_bias_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    cycle_bias_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    actual_success_rate: Mapped[float] = mapped_column(Float, nullable=False)
    avg_predicted_success_probability: Mapped[float] = mapped_column(Float, nullable=False)
    suggested_success_adjustment: Mapped[float] = mapped_column(Float, nullable=False)
    region_adjustments_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    success_adjustment_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        index=True,
    )
