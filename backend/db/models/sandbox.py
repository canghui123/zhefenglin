from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from db.base import Base


class SandboxResult(Base):
    __tablename__ = "sandbox_results"

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
    car_description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    entry_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    overdue_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    che300_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    daily_parking: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    input_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    path_a_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    path_b_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    path_c_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    path_d_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    path_e_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    best_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    report_pdf_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    report_storage_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
