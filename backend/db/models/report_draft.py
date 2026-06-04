"""B3 — Report draft persistence model.

Report drafts get their own table (instead of living inside
agent_runs.output_json) so we can attach a proper status machine,
admin review trail, and distribution gates to every report.

State machine:
    draft ─→ submitted ─→ accepted     (admin only; widens distribution)
              │      ╲
              │       ╲→ rejected
              ↓
            needs_revision → (back to draft via edit, or another submit)

distribution stays "draft_only" until an admin accepts. Even then,
widening to "internal" or "external" requires explicit admin action;
no agent or non-admin user can do it automatically.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ReportDraft(Base):
    __tablename__ = "report_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_run_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # report_type: executive_summary / asset_package_brief / buyer_offer_memo /
    #              weekly_operation_report / custom
    report_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # status: draft / submitted / accepted / rejected / needs_revision
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft", index=True
    )
    content_json: Mapped[str] = mapped_column(Text, nullable=False)
    # distribution: draft_only / internal / external
    # Locked to draft_only unless an admin transitions status to accepted.
    distribution: Mapped[str] = mapped_column(
        String(32), nullable=False, default="draft_only"
    )
    review_checklist_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_context_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    requires_human_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    # Related business object (optional)
    related_object_type: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True
    )
    related_object_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # creator / submitter / reviewer trail
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    submitted_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
