"""内测申请（access request）表。

公开注册关闭后，访客通过 `/api/auth/access-request` 留资，
运营/admin 在后台审核后再用 `scripts/create_admin.py` 开通账号。

这张表只做最简 lead 捕获，不绑定租户；approve/reject 暂时走人工。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Text, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class AccessRequest(Base):
    __tablename__ = "access_requests"
    __table_args__ = (
        Index("ix_access_requests_status_created_at", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    scenario: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # pending / approved / rejected / contacted
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    terms_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # 记录运营审核备注或拒绝理由
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
