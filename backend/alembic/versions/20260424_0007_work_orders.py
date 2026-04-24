"""Execution work orders.

Revision ID: 20260424_0007
Revises: 20260424_0006
Create Date: 2026-04-24
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260424_0007"
down_revision: Union[str, None] = "20260424_0006"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "work_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("order_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("target_description", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=True),
        sa.Column("source_id", sa.String(length=64), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_work_orders_tenant_id"), "work_orders", ["tenant_id"])
    op.create_index(op.f("ix_work_orders_created_by"), "work_orders", ["created_by"])
    op.create_index(op.f("ix_work_orders_order_type"), "work_orders", ["order_type"])
    op.create_index(op.f("ix_work_orders_status"), "work_orders", ["status"])
    op.create_index(op.f("ix_work_orders_source_type"), "work_orders", ["source_type"])
    op.create_index(op.f("ix_work_orders_source_id"), "work_orders", ["source_id"])
    op.create_index(op.f("ix_work_orders_created_at"), "work_orders", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_work_orders_created_at"), table_name="work_orders")
    op.drop_index(op.f("ix_work_orders_source_id"), table_name="work_orders")
    op.drop_index(op.f("ix_work_orders_source_type"), table_name="work_orders")
    op.drop_index(op.f("ix_work_orders_status"), table_name="work_orders")
    op.drop_index(op.f("ix_work_orders_order_type"), table_name="work_orders")
    op.drop_index(op.f("ix_work_orders_created_by"), table_name="work_orders")
    op.drop_index(op.f("ix_work_orders_tenant_id"), table_name="work_orders")
    op.drop_table("work_orders")
