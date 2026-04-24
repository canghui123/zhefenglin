from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class BrandRetentionProfile(Base):
    __tablename__ = "brand_retention_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    match_keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retention_factor: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    base_monthly_depreciation: Mapped[float] = mapped_column(Float, default=0.015, nullable=False)
    age_decay_factor: Mapped[float] = mapped_column(Float, default=0.018, nullable=False)
    new_energy_tech_discount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_new_energy: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class RegionDisposalCoefficient(Base):
    __tablename__ = "region_disposal_coefficients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region_code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    province: Mapped[str] = mapped_column(String, nullable=False, index=True)
    city: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    liquidity_speed_factor: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    legal_efficiency_factor: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    towing_cost_factor: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
