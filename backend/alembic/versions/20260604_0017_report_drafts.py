"""Report drafts table with status machine.

B3 — give AI-generated report drafts their own lifecycle instead of
sitting inside agent_runs.output_json. States: draft -> submitted ->
accepted / rejected / needs_revision. Distribution can only widen
past draft_only once an admin has accepted.

Revision ID: 20260604_0017
Revises: 20260523_0016
Create Date: 2026-06-04
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260604_0017"
down_revision: Union[str, None] = "20260523_0016"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "report_drafts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_run_id",
            sa.Integer(),
            sa.ForeignKey("agent_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("report_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("content_json", sa.Text(), nullable=False),
        sa.Column(
            "distribution",
            sa.String(length=32),
            nullable=False,
            server_default="draft_only",
        ),
        sa.Column("review_checklist_json", sa.Text(), nullable=True),
        sa.Column("source_context_json", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column(
            "requires_human_review",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        # related object (asset_package / portfolio / buyer_offer)
        sa.Column("related_object_type", sa.String(length=64), nullable=True),
        sa.Column("related_object_id", sa.String(length=64), nullable=True),
        # creator / submit / review trail
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "submitted_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column(
            "reviewed_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        op.f("ix_report_drafts_tenant_id"), "report_drafts", ["tenant_id"]
    )
    op.create_index(
        op.f("ix_report_drafts_agent_run_id"),
        "report_drafts",
        ["agent_run_id"],
    )
    op.create_index(
        op.f("ix_report_drafts_status"), "report_drafts", ["status"]
    )
    op.create_index(
        op.f("ix_report_drafts_report_type"),
        "report_drafts",
        ["report_type"],
    )
    op.create_index(
        op.f("ix_report_drafts_created_by"),
        "report_drafts",
        ["created_by"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_report_drafts_created_by"), table_name="report_drafts")
    op.drop_index(op.f("ix_report_drafts_report_type"), table_name="report_drafts")
    op.drop_index(op.f("ix_report_drafts_status"), table_name="report_drafts")
    op.drop_index(op.f("ix_report_drafts_agent_run_id"), table_name="report_drafts")
    op.drop_index(op.f("ix_report_drafts_tenant_id"), table_name="report_drafts")
    op.drop_table("report_drafts")
