"""Customer data import staging tables."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class DataImportBatch(Base):
    __tablename__ = "data_import_batches"

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
    import_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source_system: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    storage_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="parsed", index=True)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    rows: Mapped[list["DataImportRow"]] = relationship(
        "DataImportRow",
        back_populates="batch",
        cascade="all, delete-orphan",
    )


class DataImportRow(Base):
    __tablename__ = "data_import_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("data_import_batches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    row_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    asset_identifier: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    contract_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    debtor_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    car_description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    vin: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    license_plate: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    province: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    city: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    overdue_bucket: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    overdue_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    overdue_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    loan_principal: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    vehicle_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recovered_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    gps_last_seen: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    errors_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_json: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    batch: Mapped[DataImportBatch] = relationship("DataImportBatch", back_populates="rows")
