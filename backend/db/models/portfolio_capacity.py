"""Tenant-level disposal capacity settings."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class PortfolioCapacitySetting(Base):
    __tablename__ = "portfolio_capacity_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_portfolio_capacity_settings_tenant"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    monthly_towing_capacity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=80
    )
    monthly_litigation_capacity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=40
    )
    monthly_auction_capacity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100
    )
    monthly_collection_capacity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=220
    )
    inventory_yard_capacity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=180
    )
    monthly_disposal_budget: Mapped[float] = mapped_column(
        Float, nullable=False, default=2_000_000
    )
    legal_team_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=35)
    external_vendor_capacity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=80
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
