"""Schemas for customer data import staging."""

from typing import Optional

from pydantic import BaseModel, Field


class DataImportError(BaseModel):
    field: str
    message: str


class DataImportRowOut(BaseModel):
    id: int
    batch_id: int
    row_number: int
    row_status: str
    asset_identifier: Optional[str] = None
    contract_number: Optional[str] = None
    debtor_name: Optional[str] = None
    car_description: Optional[str] = None
    vin: Optional[str] = None
    license_plate: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    overdue_bucket: Optional[str] = None
    overdue_days: Optional[int] = None
    overdue_amount: Optional[int] = None
    loan_principal: Optional[int] = None
    vehicle_value: Optional[int] = None
    recovered_status: Optional[str] = None
    gps_last_seen: Optional[str] = None
    errors: list[DataImportError] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)
    normalized: dict = Field(default_factory=dict)
    created_at: str


class DataImportBatchOut(BaseModel):
    id: int
    tenant_id: int
    created_by: Optional[int] = None
    import_type: str
    filename: str
    source_system: Optional[str] = None
    storage_key: Optional[str] = None
    status: str
    total_rows: int
    success_rows: int
    error_rows: int
    created_at: str


class DataImportUploadResult(BaseModel):
    batch: DataImportBatchOut
    rows_preview: list[DataImportRowOut]
    detected_columns: dict[str, str]
    unmapped_columns: list[str]


class DataImportRowsPage(BaseModel):
    batch: DataImportBatchOut
    rows: list[DataImportRowOut]


class DataImportBatchUpdate(BaseModel):
    filename: Optional[str] = Field(default=None, min_length=1, max_length=255)
    source_system: Optional[str] = Field(default=None, max_length=120)


class DataImportBatchDeleteResult(BaseModel):
    id: int
    status: str
    message: str


class DataImportRowUpdate(BaseModel):
    asset_identifier: Optional[str] = Field(default=None, max_length=120)
    contract_number: Optional[str] = Field(default=None, max_length=120)
    debtor_name: Optional[str] = Field(default=None, max_length=120)
    car_description: Optional[str] = Field(default=None, max_length=255)
    vin: Optional[str] = Field(default=None, max_length=80)
    license_plate: Optional[str] = Field(default=None, max_length=40)
    province: Optional[str] = Field(default=None, max_length=64)
    city: Optional[str] = Field(default=None, max_length=64)
    overdue_bucket: Optional[str] = Field(default=None, max_length=64)
    overdue_days: Optional[int] = Field(default=None, ge=0)
    overdue_amount: Optional[int] = Field(default=None, ge=0)
    loan_principal: Optional[int] = Field(default=None, ge=0)
    vehicle_value: Optional[int] = Field(default=None, ge=0)
    recovered_status: Optional[str] = Field(default=None, max_length=64)
    gps_last_seen: Optional[str] = Field(default=None, max_length=120)
