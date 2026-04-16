from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class TenantSubscription(Base):
    __tablename__ = "tenant_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    custom_pricing_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    monthly_budget_limit: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    alert_threshold_percent: Mapped[float] = mapped_column(
        Float, nullable=False, default=80
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FeatureEntitlement(Base):
    __tablename__ = "feature_entitlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="plan")
    plan_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=True,
    )
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    feature_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    config_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
