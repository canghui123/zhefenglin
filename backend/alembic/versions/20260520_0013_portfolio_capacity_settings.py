"""Persist portfolio capacity settings.

Revision ID: 20260520_0013
Revises: 20260515_0012
Create Date: 2026-05-20
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260520_0013"
down_revision: Union[str, None] = "20260515_0012"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_capacity_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("monthly_towing_capacity", sa.Integer(), nullable=False),
        sa.Column("monthly_litigation_capacity", sa.Integer(), nullable=False),
        sa.Column("monthly_auction_capacity", sa.Integer(), nullable=False),
        sa.Column("monthly_collection_capacity", sa.Integer(), nullable=False),
        sa.Column("inventory_yard_capacity", sa.Integer(), nullable=False),
        sa.Column("monthly_disposal_budget", sa.Float(), nullable=False),
        sa.Column("legal_team_capacity", sa.Integer(), nullable=False),
        sa.Column("external_vendor_capacity", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_portfolio_capacity_settings_tenant"),
    )
    op.create_index(
        op.f("ix_portfolio_capacity_settings_tenant_id"),
        "portfolio_capacity_settings",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_portfolio_capacity_settings_tenant_id"),
        table_name="portfolio_capacity_settings",
    )
    op.drop_table("portfolio_capacity_settings")
