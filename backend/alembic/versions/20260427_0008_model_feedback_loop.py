"""Model feedback loop.

Revision ID: 20260427_0008
Revises: 20260424_0007
Create Date: 2026-04-27
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260427_0008"
down_revision: Union[str, None] = "20260424_0007"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "disposal_outcomes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("source_id", sa.String(length=100), nullable=True),
        sa.Column("asset_identifier", sa.String(length=120), nullable=False),
        sa.Column("strategy_path", sa.String(length=64), nullable=False),
        sa.Column("province", sa.String(length=64), nullable=True),
        sa.Column("city", sa.String(length=64), nullable=True),
        sa.Column("predicted_recovery_amount", sa.Float(), nullable=False),
        sa.Column("actual_recovery_amount", sa.Float(), nullable=False),
        sa.Column("predicted_cycle_days", sa.Integer(), nullable=False),
        sa.Column("actual_cycle_days", sa.Integer(), nullable=False),
        sa.Column("predicted_success_probability", sa.Float(), nullable=False),
        sa.Column("outcome_status", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_disposal_outcomes_tenant_id"), "disposal_outcomes", ["tenant_id"])
    op.create_index(op.f("ix_disposal_outcomes_created_by"), "disposal_outcomes", ["created_by"])
    op.create_index(op.f("ix_disposal_outcomes_source_type"), "disposal_outcomes", ["source_type"])
    op.create_index(op.f("ix_disposal_outcomes_source_id"), "disposal_outcomes", ["source_id"])
    op.create_index(op.f("ix_disposal_outcomes_asset_identifier"), "disposal_outcomes", ["asset_identifier"])
    op.create_index(op.f("ix_disposal_outcomes_strategy_path"), "disposal_outcomes", ["strategy_path"])
    op.create_index(op.f("ix_disposal_outcomes_province"), "disposal_outcomes", ["province"])
    op.create_index(op.f("ix_disposal_outcomes_city"), "disposal_outcomes", ["city"])
    op.create_index(op.f("ix_disposal_outcomes_outcome_status"), "disposal_outcomes", ["outcome_status"])
    op.create_index(op.f("ix_disposal_outcomes_created_at"), "disposal_outcomes", ["created_at"])

    op.create_table(
        "model_learning_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("recovery_bias_ratio", sa.Float(), nullable=False),
        sa.Column("cycle_bias_ratio", sa.Float(), nullable=False),
        sa.Column("actual_success_rate", sa.Float(), nullable=False),
        sa.Column("avg_predicted_success_probability", sa.Float(), nullable=False),
        sa.Column("suggested_success_adjustment", sa.Float(), nullable=False),
        sa.Column("region_adjustments_json", sa.Text(), nullable=True),
        sa.Column("applied", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_model_learning_runs_tenant_id"), "model_learning_runs", ["tenant_id"])
    op.create_index(op.f("ix_model_learning_runs_created_by"), "model_learning_runs", ["created_by"])
    op.create_index(op.f("ix_model_learning_runs_created_at"), "model_learning_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_model_learning_runs_created_at"), table_name="model_learning_runs")
    op.drop_index(op.f("ix_model_learning_runs_created_by"), table_name="model_learning_runs")
    op.drop_index(op.f("ix_model_learning_runs_tenant_id"), table_name="model_learning_runs")
    op.drop_table("model_learning_runs")
    op.drop_index(op.f("ix_disposal_outcomes_created_at"), table_name="disposal_outcomes")
    op.drop_index(op.f("ix_disposal_outcomes_outcome_status"), table_name="disposal_outcomes")
    op.drop_index(op.f("ix_disposal_outcomes_city"), table_name="disposal_outcomes")
    op.drop_index(op.f("ix_disposal_outcomes_province"), table_name="disposal_outcomes")
    op.drop_index(op.f("ix_disposal_outcomes_strategy_path"), table_name="disposal_outcomes")
    op.drop_index(op.f("ix_disposal_outcomes_asset_identifier"), table_name="disposal_outcomes")
    op.drop_index(op.f("ix_disposal_outcomes_source_id"), table_name="disposal_outcomes")
    op.drop_index(op.f("ix_disposal_outcomes_source_type"), table_name="disposal_outcomes")
    op.drop_index(op.f("ix_disposal_outcomes_created_by"), table_name="disposal_outcomes")
    op.drop_index(op.f("ix_disposal_outcomes_tenant_id"), table_name="disposal_outcomes")
    op.drop_table("disposal_outcomes")
