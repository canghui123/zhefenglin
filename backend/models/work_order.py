from pydantic import BaseModel, Field, field_validator
from typing import Optional


WORK_ORDER_TYPES = {"towing", "legal_document", "auction_push"}
WORK_ORDER_STATUSES = {"pending", "in_progress", "completed", "cancelled"}
WORK_ORDER_PRIORITIES = {"low", "normal", "high", "urgent"}


class WorkOrderCreate(BaseModel):
    order_type: str = Field(..., description="towing/legal_document/auction_push")
    title: str = Field(..., min_length=1, max_length=200)
    target_description: Optional[str] = None
    priority: str = "normal"
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    payload: dict = Field(default_factory=dict)

    @field_validator("order_type")
    @classmethod
    def validate_order_type(cls, value: str) -> str:
        if value not in WORK_ORDER_TYPES:
            raise ValueError("无效的工单类型")
        return value

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        if value not in WORK_ORDER_PRIORITIES:
            raise ValueError("无效的优先级")
        return value


class WorkOrderStatusUpdate(BaseModel):
    status: str
    result: dict = Field(default_factory=dict)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in WORK_ORDER_STATUSES:
            raise ValueError("无效的工单状态")
        return value


class WorkOrderOut(BaseModel):
    id: int
    tenant_id: int
    created_by: Optional[int] = None
    order_type: str
    status: str
    priority: str
    title: str
    target_description: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    payload: dict = Field(default_factory=dict)
    result: dict = Field(default_factory=dict)
    created_at: str
    updated_at: str
