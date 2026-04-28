from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
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


class SandboxSimulationBatch(Base):
    __tablename__ = "sandbox_simulation_batches"

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
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed", index=True)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    items: Mapped[list["SandboxSimulationBatchItem"]] = relationship(
        "SandboxSimulationBatchItem",
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class SandboxSimulationBatchItem(Base):
    __tablename__ = "sandbox_simulation_batch_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sandbox_simulation_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sandbox_result_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("sandbox_results.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    row_id: Mapped[str] = mapped_column(String(120), nullable=False)
    row_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    row_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    car_description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    overdue_bucket: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    overdue_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    che300_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    best_path: Mapped[Optional[str]] = mapped_column(String(8), nullable=True, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    batch: Mapped[SandboxSimulationBatch] = relationship(
        "SandboxSimulationBatch",
        back_populates="items",
    )
    result: Mapped[Optional[SandboxResult]] = relationship("SandboxResult")
