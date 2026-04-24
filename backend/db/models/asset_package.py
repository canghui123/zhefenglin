from typing import List, Optional
from sqlalchemy import String, Integer, Float, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from db.base import Base


class AssetPackage(Base):
    __tablename__ = "asset_packages"

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
    )
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    upload_filename: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    storage_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    total_assets: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parameters_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    results_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    assets: Mapped[List["Asset"]] = relationship(
        back_populates="package", cascade="all, delete-orphan"
    )


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    package_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("asset_packages.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    car_description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    vin: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    first_registration: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    gps_online: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    insurance_lapsed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ownership_transferred: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    loan_principal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    buyout_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    province: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    region_code: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    matched_model_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    che300_valuation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    depreciation_30d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    depreciation_60d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_revenue: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net_profit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_flags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    package: Mapped[AssetPackage] = relationship(back_populates="assets")
