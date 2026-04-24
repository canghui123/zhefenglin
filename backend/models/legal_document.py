"""Schemas for legal document generation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


LEGAL_DOCUMENT_TYPES = {
    "civil_complaint",
    "preservation_application",
    "special_procedure_application",
}


class LegalDocumentGenerateRequest(BaseModel):
    document_type: str = Field(..., description="civil_complaint/preservation_application/special_procedure_application")
    debtor_name: str = Field(..., min_length=1, max_length=100)
    creditor_name: str = Field(default="某汽车金融公司", min_length=1, max_length=100)
    car_description: str = Field(..., min_length=1, max_length=300)
    contract_number: Optional[str] = Field(default=None, max_length=100)
    overdue_amount: float = Field(..., ge=0)
    vehicle_value: Optional[float] = Field(default=None, ge=0)
    facts: Optional[str] = Field(default=None, max_length=2000)
    claims: list[str] = Field(default_factory=list, max_length=8)
    work_order_id: Optional[int] = None

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, value: str) -> str:
        if value not in LEGAL_DOCUMENT_TYPES:
            raise ValueError("无效的法务材料类型")
        return value

    @field_validator("claims")
    @classmethod
    def validate_claims(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]


class LegalDocumentResult(BaseModel):
    document_type: str
    title: str
    html: str
    plain_text: str
    generated_at: datetime
    work_order_id: Optional[int] = None
