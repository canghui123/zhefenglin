"""Schemas for disposal outcome feedback and model learning."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


OUTCOME_STATUSES = {"success", "partial", "failed"}


class DisposalOutcomeCreate(BaseModel):
    asset_identifier: str = Field(..., min_length=1, max_length=120)
    strategy_path: str = Field(..., min_length=1, max_length=64)
    source_type: Optional[str] = Field(default=None, max_length=64)
    source_id: Optional[str] = Field(default=None, max_length=100)
    province: Optional[str] = Field(default=None, max_length=64)
    city: Optional[str] = Field(default=None, max_length=64)
    predicted_recovery_amount: float = Field(..., ge=0)
    actual_recovery_amount: float = Field(..., ge=0)
    predicted_cycle_days: int = Field(..., ge=1)
    actual_cycle_days: int = Field(..., ge=1)
    predicted_success_probability: float = Field(..., ge=0, le=1)
    outcome_status: str = "success"
    notes: Optional[str] = Field(default=None, max_length=1000)
    metadata: dict = Field(default_factory=dict)

    @field_validator("outcome_status")
    @classmethod
    def validate_outcome_status(cls, value: str) -> str:
        if value not in OUTCOME_STATUSES:
            raise ValueError("无效的处置结果状态")
        return value


class DisposalOutcomeOut(BaseModel):
    id: int
    tenant_id: int
    created_by: Optional[int] = None
    asset_identifier: str
    strategy_path: str
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None
    predicted_recovery_amount: float
    actual_recovery_amount: float
    predicted_cycle_days: int
    actual_cycle_days: int
    predicted_success_probability: float
    outcome_status: str
    notes: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    created_at: str


class RegionAdjustmentSuggestion(BaseModel):
    province: Optional[str] = None
    city: Optional[str] = None
    sample_count: int
    recovery_bias_ratio: float
    cycle_bias_ratio: float
    liquidity_speed_multiplier: float
    legal_efficiency_multiplier: float


class StrategyAdjustmentSuggestion(BaseModel):
    strategy_path: str
    strategy_name: str
    sample_count: int
    actual_success_rate: float
    avg_predicted_success_probability: float
    suggested_success_adjustment: float


class ModelFeedbackSummary(BaseModel):
    sample_count: int
    recovery_bias_ratio: float
    cycle_bias_ratio: float
    actual_success_rate: float
    avg_predicted_success_probability: float
    suggested_success_adjustment: float
    active_success_adjustment: float = 0.0
    active_success_adjustment_run_id: Optional[int] = None
    region_adjustments: list[RegionAdjustmentSuggestion]
    strategy_adjustments: list[StrategyAdjustmentSuggestion]
    active_strategy_adjustments: list[StrategyAdjustmentSuggestion] = Field(default_factory=list)


class ModelLearningRunCreate(BaseModel):
    apply_region_adjustments: bool = False
    apply_success_adjustment: bool = False


class ModelLearningRunOut(BaseModel):
    id: int
    tenant_id: int
    created_by: Optional[int] = None
    sample_count: int
    recovery_bias_ratio: float
    cycle_bias_ratio: float
    actual_success_rate: float
    avg_predicted_success_probability: float
    suggested_success_adjustment: float
    region_adjustments: list[RegionAdjustmentSuggestion]
    strategy_adjustments: list[StrategyAdjustmentSuggestion] = Field(default_factory=list)
    applied: bool
    success_adjustment_applied: bool
    created_at: str
