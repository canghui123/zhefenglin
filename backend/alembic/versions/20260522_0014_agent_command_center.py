"""Agent command center tables.

Revision ID: 20260522_0014
Revises: 20260520_0013
Create Date: 2026-05-22
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260522_0014"
down_revision: Union[str, None] = "20260520_0013"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("agent_type", sa.String(length=64), nullable=False),
        sa.Column("input_json", sa.Text(), nullable=False),
        sa.Column("output_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_runs_agent_type"), "agent_runs", ["agent_type"])
    op.create_index(op.f("ix_agent_runs_created_by"), "agent_runs", ["created_by"])
    op.create_index(op.f("ix_agent_runs_started_at"), "agent_runs", ["started_at"])
    op.create_index(op.f("ix_agent_runs_status"), "agent_runs", ["status"])
    op.create_index(op.f("ix_agent_runs_tenant_id"), "agent_runs", ["tenant_id"])

    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("agent_run_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_tasks_agent_run_id"), "agent_tasks", ["agent_run_id"])
    op.create_index(op.f("ix_agent_tasks_created_by"), "agent_tasks", ["created_by"])
    op.create_index(op.f("ix_agent_tasks_status"), "agent_tasks", ["status"])
    op.create_index(op.f("ix_agent_tasks_tenant_id"), "agent_tasks", ["tenant_id"])

    op.create_table(
        "agent_recommendations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("agent_run_id", sa.Integer(), nullable=True),
        sa.Column("recommendation_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_recommendations_agent_run_id"), "agent_recommendations", ["agent_run_id"])
    op.create_index(op.f("ix_agent_recommendations_created_by"), "agent_recommendations", ["created_by"])
    op.create_index(
        op.f("ix_agent_recommendations_recommendation_type"),
        "agent_recommendations",
        ["recommendation_type"],
    )
    op.create_index(op.f("ix_agent_recommendations_tenant_id"), "agent_recommendations", ["tenant_id"])

    op.create_table(
        "decision_audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("agent_run_id", sa.Integer(), nullable=True),
        sa.Column("decision_type", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("before_json", sa.Text(), nullable=True),
        sa.Column("after_json", sa.Text(), nullable=True),
        sa.Column("requires_human_review", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_decision_audit_logs_decision_type"), "decision_audit_logs", ["decision_type"])
    op.create_index(op.f("ix_decision_audit_logs_action"), "decision_audit_logs", ["action"])
    op.create_index(op.f("ix_decision_audit_logs_actor_user_id"), "decision_audit_logs", ["actor_user_id"])
    op.create_index(op.f("ix_decision_audit_logs_agent_run_id"), "decision_audit_logs", ["agent_run_id"])
    op.create_index(op.f("ix_decision_audit_logs_tenant_id"), "decision_audit_logs", ["tenant_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_decision_audit_logs_tenant_id"), table_name="decision_audit_logs")
    op.drop_index(op.f("ix_decision_audit_logs_agent_run_id"), table_name="decision_audit_logs")
    op.drop_index(op.f("ix_decision_audit_logs_actor_user_id"), table_name="decision_audit_logs")
    op.drop_index(op.f("ix_decision_audit_logs_action"), table_name="decision_audit_logs")
    op.drop_index(op.f("ix_decision_audit_logs_decision_type"), table_name="decision_audit_logs")
    op.drop_table("decision_audit_logs")

    op.drop_index(op.f("ix_agent_recommendations_tenant_id"), table_name="agent_recommendations")
    op.drop_index(op.f("ix_agent_recommendations_recommendation_type"), table_name="agent_recommendations")
    op.drop_index(op.f("ix_agent_recommendations_created_by"), table_name="agent_recommendations")
    op.drop_index(op.f("ix_agent_recommendations_agent_run_id"), table_name="agent_recommendations")
    op.drop_table("agent_recommendations")

    op.drop_index(op.f("ix_agent_tasks_tenant_id"), table_name="agent_tasks")
    op.drop_index(op.f("ix_agent_tasks_status"), table_name="agent_tasks")
    op.drop_index(op.f("ix_agent_tasks_created_by"), table_name="agent_tasks")
    op.drop_index(op.f("ix_agent_tasks_agent_run_id"), table_name="agent_tasks")
    op.drop_table("agent_tasks")

    op.drop_index(op.f("ix_agent_runs_tenant_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_status"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_started_at"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_created_by"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_agent_type"), table_name="agent_runs")
    op.drop_table("agent_runs")
