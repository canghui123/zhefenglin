from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    module: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1)
    unit_cost_internal: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    unit_price_external: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    estimated_cost_total: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    related_object_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    related_object_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )


class CostSnapshot(Base):
    __tablename__ = "cost_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    vin_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    condition_pricing_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    che300_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    estimated_revenue: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    estimated_gross_profit: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    extra_metrics_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
