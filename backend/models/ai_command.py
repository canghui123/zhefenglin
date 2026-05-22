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


class AgentRunCreate(BaseModel):
    question: str = ""
    agent_type: Optional[str] = None
    asset_package_id: Optional[int] = None
    buyer_offer_price: Optional[float] = None
    buyer_offer_note: Optional[str] = None


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
    agent_run_id: Optional[int] = None
    decision_type: str
    action: str
    actor_user_id: Optional[int] = None
    requires_human_review: bool
    created_at: str
    after: dict[str, Any] = Field(default_factory=dict)
