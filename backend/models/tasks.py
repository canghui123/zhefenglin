from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


TaskStatus = Literal["pending", "assigned", "in_progress", "blocked", "done", "cancelled"]
TaskPriority = Literal["high", "medium", "low", "normal"]


class DisposalTaskCreate(BaseModel):
    task_type: str
    title: str
    priority: TaskPriority = "medium"
    target_description: Optional[str] = None
    source_type: Optional[str] = "manual"
    source_id: Optional[str] = None
    owner_user_id: Optional[int] = None
    expected_recovery: Optional[float] = None
    expected_cost: Optional[float] = None
    deadline: Optional[str] = None
    evidence_files: list[str] = Field(default_factory=list)


class DisposalTaskUpdate(BaseModel):
    task_type: Optional[str] = None
    title: Optional[str] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    target_description: Optional[str] = None
    owner_user_id: Optional[int] = None
    expected_recovery: Optional[float] = None
    expected_cost: Optional[float] = None
    deadline: Optional[str] = None
    evidence_files: Optional[list[str]] = None
    result_note: Optional[str] = None
    actual_recovery: Optional[float] = None
    variance_reason: Optional[str] = None


class DisposalTaskAssign(BaseModel):
    owner_user_id: int


class DisposalTaskComplete(BaseModel):
    actual_recovery: Optional[float] = None
    result_note: Optional[str] = None
    variance_reason: Optional[str] = None
    evidence_files: list[str] = Field(default_factory=list)


class DisposalTaskOut(BaseModel):
    id: int
    tenant_id: int
    task_type: str
    status: str
    priority: str
    title: str
    target_description: Optional[str] = None
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    owner_user_id: Optional[int] = None
    expected_recovery: Optional[float] = None
    expected_cost: Optional[float] = None
    deadline: Optional[str] = None
    evidence_files: list[str] = Field(default_factory=list)
    result_note: Optional[str] = None
    actual_recovery: Optional[float] = None
    variance_reason: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
