from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class TenantDeploymentProfile(Base):
    __tablename__ = "tenant_deployment_profiles"
    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_tenant_deployment_profiles_tenant_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    deployment_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="saas_dedicated"
    )
    delivery_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="planning"
    )
    access_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sso_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sso_provider: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sso_login_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    storage_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default="platform_managed"
    )
    backup_level: Mapped[str] = mapped_column(String(32), nullable=False, default="standard")
    environment_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    handover_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
