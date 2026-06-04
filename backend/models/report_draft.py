"""B3 — Report draft API/business models.

Pydantic schemas for report drafts. Status machine constants and
transition rules live here so both repository and API can share them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# Status machine ─────────────────────────────────────────────────────
ReportStatus = Literal["draft", "submitted", "accepted", "rejected", "needs_revision"]
ReportDistribution = Literal["draft_only", "internal", "external"]
ReportType = Literal[
    "executive_summary",
    "asset_package_brief",
    "buyer_offer_memo",
    "weekly_operation_report",
    "custom",
]
ReportTransitionAction = Literal[
    "submit",
    "accept",
    "reject",
    "request_revision",
]


# Allowed status transitions. Anyone trying to make a leap not in this
# table gets a 400 — the repository / API layer is the single source of
# truth for the state machine.
ALLOWED_TRANSITIONS: dict[ReportStatus, set[ReportStatus]] = {
    "draft": {"submitted"},
    "submitted": {"accepted", "rejected", "needs_revision"},
    "accepted": set(),  # terminal until someone re-creates a follow-up draft
    "rejected": set(),
    "needs_revision": {"submitted"},  # author edits and re-submits
}

# Distribution widening rules. Distribution stays draft_only unless an
# admin actively transitions status to "accepted"; even then the admin
# has to set distribution explicitly. Agents and non-admin users can
# never widen.
DRAFT_ONLY_DISTRIBUTION: ReportDistribution = "draft_only"


# CRUD I/O models ────────────────────────────────────────────────────

class ReportDraftCreate(BaseModel):
    """Create a draft manually (without an Agent run).
    Used for follow-up drafts, custom reports, etc.
    """

    report_type: ReportType
    title: str = Field(..., max_length=255)
    content_json: dict[str, Any] = Field(default_factory=dict)
    review_checklist_json: Optional[dict[str, Any]] = None
    source_context_json: Optional[dict[str, Any]] = None
    related_object_type: Optional[str] = Field(default=None, max_length=64)
    related_object_id: Optional[str] = Field(default=None, max_length=64)
    confidence_score: Optional[float] = Field(default=None, ge=0, le=1)
    agent_run_id: Optional[int] = None


class ReportDraftUpdate(BaseModel):
    """Edit draft fields (title / content / checklist) while status
    is still 'draft' or 'needs_revision'. Once submitted, only an
    admin transition can change state."""

    title: Optional[str] = Field(default=None, max_length=255)
    content_json: Optional[dict[str, Any]] = None
    review_checklist_json: Optional[dict[str, Any]] = None


class ReportDraftTransition(BaseModel):
    """Status-machine transition request."""

    action: ReportTransitionAction
    notes: Optional[str] = Field(default=None, max_length=2000)
    # admin can widen distribution only when accepting
    distribution: Optional[ReportDistribution] = None


class ReportDraftOut(BaseModel):
    """API response model."""

    id: int
    tenant_id: int
    agent_run_id: Optional[int] = None
    report_type: str
    title: str
    status: str
    content_json: dict[str, Any] = Field(default_factory=dict)
    distribution: str
    review_checklist_json: Optional[dict[str, Any]] = None
    source_context_json: Optional[dict[str, Any]] = None
    confidence_score: Optional[float] = None
    requires_human_review: bool
    related_object_type: Optional[str] = None
    related_object_id: Optional[str] = None
    created_by: Optional[int] = None
    submitted_by: Optional[int] = None
    submitted_at: Optional[datetime] = None
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ReportDraftListItem(BaseModel):
    """Slim list-view model (no big content_json blob)."""

    id: int
    report_type: str
    title: str
    status: str
    distribution: str
    confidence_score: Optional[float] = None
    related_object_type: Optional[str] = None
    related_object_id: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
