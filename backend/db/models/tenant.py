"""Tenant ORM model.

A tenant represents a logical customer/organisation. Every business row
(asset_packages, sandbox_results, portfolio_snapshots, ...) is scoped to
exactly one tenant. Users gain access to a tenant via the `memberships`
table; their currently active tenant is stored in `users.default_tenant_id`.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Boolean, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        UniqueConstraint("code", name="uq_tenants_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
