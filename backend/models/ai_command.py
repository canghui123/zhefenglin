from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


AgentType = Literal[
    "asset_package_diagnosis_agent",
    "valuation_analysis_agent",
    "pricing_strategy_agent",
    "buyer_offer_analysis_agent",
    "operation_planning_agent",
    "task_generation_agent",
    "report_generation_agent",
    "cost_control_agent",
]


class AgentEvidence(BaseModel):
    source: str
    label: str
    value: Any = None
    evidence_source: Optional[str] = None
    related_object_type: Optional[str] = None
    related_object_id: Optional[str] = None
    calculation_basis: Optional[str] = None
    data_quality_notes: Optional[str] = None


class AgentOutput(BaseModel):
    summary: str
    key_findings: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    risk_warnings: list[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0, le=1)
    evidence: list[AgentEvidence] = Field(default_factory=list)
    requires_human_review: bool = True
    agent_status: str = "rules_based"


class AgentRunCreate(BaseModel):
    question: str = ""
    agent_type: Optional[str] = None
    asset_package_id: Optional[int] = None
    buyer_offer_price: Optional[float] = None
    buyer_offer_note: Optional[str] = None
    expected_vin_calls: Optional[int] = None
    expected_condition_pricing_calls: Optional[int] = None
    expected_ai_reports: Optional[int] = None
    single_task_budget: Optional[float] = None
    report_type: Optional[str] = None
    rule_scenario: Optional[str] = None


class AgentRunOut(BaseModel):
    id: int
    tenant_id: int
    agent_type: str
    status: str
    created_by: Optional[int] = None
    started_at: str
    finished_at: Optional[str] = None
    requires_human_review: bool
    input: dict[str, Any] = Field(default_factory=dict)
    output: AgentOutput


class AgentTaskOut(BaseModel):
    id: int
    agent_run_id: Optional[int] = None
    title: str
    task_type: str
    priority: str
    status: str
    requires_human_review: bool
    created_at: str
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentTaskDecisionCreate(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=1000)


class AgentRecommendationOut(BaseModel):
    id: int
    agent_run_id: Optional[int] = None
    recommendation_type: str
    title: str
    summary: str
    confidence_score: float
    requires_human_review: bool
    created_at: str


class AgentWorkbenchItem(BaseModel):
    agent_type: str
    name: str
    stage: str
    status: str
    min_role: str


class AiCommandOverview(BaseModel):
    today_overview: dict[str, Any]
    ai_today_judgment: AgentOutput
    agent_workbench: list[AgentWorkbenchItem]
    pending_tasks: list[AgentTaskOut]
    pending_approvals: list[AgentRecommendationOut]
    recent_runs: list[AgentRunOut]
    suggested_prompts: list[str]
    role_scope: str


class DecisionAuditLogOut(BaseModel):
    id: int
    tenant_id: int
    agent_run_id: Optional[int] = None
    decision_type: str
    action: str
    actor_user_id: Optional[int] = None
    requires_human_review: bool
    created_at: str
    after: dict[str, Any] = Field(default_factory=dict)


class AgentRuleSettings(BaseModel):
    operation_high_priority_limit: int = Field(default=5, ge=1, le=20)
    operation_data_gap_min_count: int = Field(default=1, ge=0, le=10000)
    task_max_drafts: int = Field(default=8, ge=1, le=20)
    task_urgent_deadline_days: int = Field(default=1, ge=0, le=30)
    task_normal_deadline_days: int = Field(default=7, ge=1, le=90)
    cost_budget_warning_percent: float = Field(default=0.8, ge=0, le=1)
    cost_condition_call_approval_threshold: int = Field(default=1, ge=1, le=100000)
    cost_ai_report_merge_threshold: int = Field(default=2, ge=1, le=1000)
    report_confidence_floor: float = Field(default=0.4, ge=0, le=1)
    report_max_sections: int = Field(default=3, ge=1, le=10)


class AgentRuleSettingsOut(AgentRuleSettings):
    tenant_id: int
    agent_type: str = "global"
    scenario: str = "default"
    version: int = 1
    is_active: bool = True
    updated_by: Optional[int] = None
    updated_at: Optional[str] = None


class AgentRuleSettingsUpsert(AgentRuleSettings):
    agent_type: str = Field(default="global", min_length=1, max_length=64)
    scenario: str = Field(default="default", min_length=1, max_length=64)
    is_active: bool = True


class AgentRuleProfileSummary(BaseModel):
    tenant_id: int
    agent_type: str
    scenario: str
    version: int
    is_active: bool
    updated_by: Optional[int] = None
    updated_at: Optional[str] = None


ReviewOutcome = Literal["accepted", "rejected", "partial", "needs_revision"]


class AgentRunReviewCreate(BaseModel):
    outcome: ReviewOutcome = "partial"
    usefulness_score: int = Field(default=3, ge=1, le=5)
    accuracy_score: int = Field(default=3, ge=1, le=5)
    accepted_actions_count: int = Field(default=0, ge=0)
    rejected_actions_count: int = Field(default=0, ge=0)
    follow_up_required: bool = False
    feedback: Optional[str] = Field(default=None, max_length=2000)


class AgentRunReviewOut(BaseModel):
    id: int
    tenant_id: int
    agent_run_id: int
    reviewer_user_id: Optional[int] = None
    outcome: str
    usefulness_score: int
    accuracy_score: int
    accepted_actions_count: int
    rejected_actions_count: int
    follow_up_required: bool
    feedback: Optional[str] = None
    created_at: str


class AgentReviewInsightOut(BaseModel):
    tenant_id: int
    review_count: int
    average_usefulness_score: float
    average_accuracy_score: float
    accepted_actions_count: int
    rejected_actions_count: int
    follow_up_required_count: int
    acceptance_rate: float
    recommendations: list[str] = Field(default_factory=list)
    requires_human_review: bool = True
