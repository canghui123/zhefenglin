from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ModelRoutingRule(Base):
    __tablename__ = "model_routing_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="global", index=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    task_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    preferred_model: Mapped[str] = mapped_column(String(128), nullable=False)
    fallback_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    allow_batch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_search: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allow_high_cost_mode: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
