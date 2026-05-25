"""AI Agent rule settings and review loop.

Revision ID: 20260523_0015
Revises: 20260522_0014
Create Date: 2026-05-23
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260523_0015"
down_revision: Union[str, None] = "20260522_0014"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "agent_rule_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("operation_high_priority_limit", sa.Integer(), nullable=False),
        sa.Column("operation_data_gap_min_count", sa.Integer(), nullable=False),
        sa.Column("task_max_drafts", sa.Integer(), nullable=False),
        sa.Column("task_urgent_deadline_days", sa.Integer(), nullable=False),
        sa.Column("task_normal_deadline_days", sa.Integer(), nullable=False),
        sa.Column("cost_budget_warning_percent", sa.Float(), nullable=False),
        sa.Column("cost_condition_call_approval_threshold", sa.Integer(), nullable=False),
        sa.Column("cost_ai_report_merge_threshold", sa.Integer(), nullable=False),
        sa.Column("report_confidence_floor", sa.Float(), nullable=False),
        sa.Column("report_max_sections", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_agent_rule_settings_tenant"),
    )
    op.create_index(op.f("ix_agent_rule_settings_tenant_id"), "agent_rule_settings", ["tenant_id"])

    op.create_table(
        "agent_run_reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("agent_run_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_user_id", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("usefulness_score", sa.Integer(), nullable=False),
        sa.Column("accuracy_score", sa.Integer(), nullable=False),
        sa.Column("accepted_actions_count", sa.Integer(), nullable=False),
        sa.Column("rejected_actions_count", sa.Integer(), nullable=False),
        sa.Column("follow_up_required", sa.Boolean(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_run_reviews_agent_run_id"), "agent_run_reviews", ["agent_run_id"])
    op.create_index(op.f("ix_agent_run_reviews_outcome"), "agent_run_reviews", ["outcome"])
    op.create_index(op.f("ix_agent_run_reviews_reviewer_user_id"), "agent_run_reviews", ["reviewer_user_id"])
    op.create_index(op.f("ix_agent_run_reviews_tenant_id"), "agent_run_reviews", ["tenant_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_run_reviews_tenant_id"), table_name="agent_run_reviews")
    op.drop_index(op.f("ix_agent_run_reviews_reviewer_user_id"), table_name="agent_run_reviews")
    op.drop_index(op.f("ix_agent_run_reviews_outcome"), table_name="agent_run_reviews")
    op.drop_index(op.f("ix_agent_run_reviews_agent_run_id"), table_name="agent_run_reviews")
    op.drop_table("agent_run_reviews")

    op.drop_index(op.f("ix_agent_rule_settings_tenant_id"), table_name="agent_rule_settings")
    op.drop_table("agent_rule_settings")
