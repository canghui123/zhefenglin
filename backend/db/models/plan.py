from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    billing_cycle_supported: Mapped[str] = mapped_column(
        String(64), nullable=False, default="monthly,yearly"
    )
    monthly_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    yearly_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    setup_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    private_deploy_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    seat_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    included_vin_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    included_condition_pricing_points: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    included_ai_reports: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    included_asset_packages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    included_sandbox_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overage_vin_unit_price: Mapped[float] = mapped_column(
        Float, nullable=False, default=0
    )
    overage_condition_pricing_unit_price: Mapped[float] = mapped_column(
        Float, nullable=False, default=0
    )
    feature_flags_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
