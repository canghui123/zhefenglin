"""Persist inventory sandbox batch simulation results.

Revision ID: 20260428_0011
Revises: 20260428_0010
Create Date: 2026-04-28
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260428_0011"
down_revision: Union[str, None] = "20260428_0010"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "sandbox_simulation_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("success_rows", sa.Integer(), nullable=False),
        sa.Column("error_rows", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_sandbox_simulation_batches_tenant_id"),
        "sandbox_simulation_batches",
        ["tenant_id"],
    )
    op.create_index(
        op.f("ix_sandbox_simulation_batches_created_by"),
        "sandbox_simulation_batches",
        ["created_by"],
    )
    op.create_index(
        op.f("ix_sandbox_simulation_batches_status"),
        "sandbox_simulation_batches",
        ["status"],
    )
    op.create_index(
        op.f("ix_sandbox_simulation_batches_created_at"),
        "sandbox_simulation_batches",
        ["created_at"],
    )

    op.create_table(
        "sandbox_simulation_batch_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("sandbox_result_id", sa.Integer(), nullable=True),
        sa.Column("row_id", sa.String(length=120), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("row_status", sa.String(length=32), nullable=False),
        sa.Column("car_description", sa.String(length=255), nullable=True),
        sa.Column("overdue_bucket", sa.String(length=64), nullable=True),
        sa.Column("overdue_amount", sa.Float(), nullable=True),
        sa.Column("che300_value", sa.Float(), nullable=True),
        sa.Column("best_path", sa.String(length=8), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("input_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["batch_id"],
            ["sandbox_simulation_batches.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["sandbox_result_id"],
            ["sandbox_results.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_sandbox_simulation_batch_items_batch_id"),
        "sandbox_simulation_batch_items",
        ["batch_id"],
    )
    op.create_index(
        op.f("ix_sandbox_simulation_batch_items_sandbox_result_id"),
        "sandbox_simulation_batch_items",
        ["sandbox_result_id"],
    )
    op.create_index(
        op.f("ix_sandbox_simulation_batch_items_row_number"),
        "sandbox_simulation_batch_items",
        ["row_number"],
    )
    op.create_index(
        op.f("ix_sandbox_simulation_batch_items_row_status"),
        "sandbox_simulation_batch_items",
        ["row_status"],
    )
    op.create_index(
        op.f("ix_sandbox_simulation_batch_items_overdue_bucket"),
        "sandbox_simulation_batch_items",
        ["overdue_bucket"],
    )
    op.create_index(
        op.f("ix_sandbox_simulation_batch_items_best_path"),
        "sandbox_simulation_batch_items",
        ["best_path"],
    )
    op.create_index(
        op.f("ix_sandbox_simulation_batch_items_created_at"),
        "sandbox_simulation_batch_items",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_sandbox_simulation_batch_items_created_at"),
        table_name="sandbox_simulation_batch_items",
    )
    op.drop_index(
        op.f("ix_sandbox_simulation_batch_items_best_path"),
        table_name="sandbox_simulation_batch_items",
    )
    op.drop_index(
        op.f("ix_sandbox_simulation_batch_items_overdue_bucket"),
        table_name="sandbox_simulation_batch_items",
    )
    op.drop_index(
        op.f("ix_sandbox_simulation_batch_items_row_status"),
        table_name="sandbox_simulation_batch_items",
    )
    op.drop_index(
        op.f("ix_sandbox_simulation_batch_items_row_number"),
        table_name="sandbox_simulation_batch_items",
    )
    op.drop_index(
        op.f("ix_sandbox_simulation_batch_items_sandbox_result_id"),
        table_name="sandbox_simulation_batch_items",
    )
    op.drop_index(
        op.f("ix_sandbox_simulation_batch_items_batch_id"),
        table_name="sandbox_simulation_batch_items",
    )
    op.drop_table("sandbox_simulation_batch_items")
    op.drop_index(
        op.f("ix_sandbox_simulation_batches_created_at"),
        table_name="sandbox_simulation_batches",
    )
    op.drop_index(
        op.f("ix_sandbox_simulation_batches_status"),
        table_name="sandbox_simulation_batches",
    )
    op.drop_index(
        op.f("ix_sandbox_simulation_batches_created_by"),
        table_name="sandbox_simulation_batches",
    )
    op.drop_index(
        op.f("ix_sandbox_simulation_batches_tenant_id"),
        table_name="sandbox_simulation_batches",
    )
    op.drop_table("sandbox_simulation_batches")
