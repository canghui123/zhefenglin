"""Decision model configuration tables.

Revision ID: 20260424_0006
Revises: 20260410_0005
Create Date: 2026-04-24
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260424_0006"
down_revision: Union[str, None] = "20260410_0005"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "brand_retention_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("vehicle_type", sa.String(), nullable=False),
        sa.Column("match_keywords", sa.Text(), nullable=True),
        sa.Column("retention_factor", sa.Float(), nullable=False),
        sa.Column("base_monthly_depreciation", sa.Float(), nullable=False),
        sa.Column("age_decay_factor", sa.Float(), nullable=False),
        sa.Column("new_energy_tech_discount", sa.Float(), nullable=False),
        sa.Column("is_new_energy", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(
        op.f("ix_brand_retention_profiles_vehicle_type"),
        "brand_retention_profiles",
        ["vehicle_type"],
    )

    op.create_table(
        "region_disposal_coefficients",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("region_code", sa.String(), nullable=False),
        sa.Column("province", sa.String(), nullable=False),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("liquidity_speed_factor", sa.Float(), nullable=False),
        sa.Column("legal_efficiency_factor", sa.Float(), nullable=False),
        sa.Column("towing_cost_factor", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("region_code"),
    )
    op.create_index(
        op.f("ix_region_disposal_coefficients_province"),
        "region_disposal_coefficients",
        ["province"],
    )
    op.create_index(
        op.f("ix_region_disposal_coefficients_city"),
        "region_disposal_coefficients",
        ["city"],
    )

    op.add_column("assets", sa.Column("province", sa.String(), nullable=True))
    op.add_column("assets", sa.Column("city", sa.String(), nullable=True))
    op.add_column("assets", sa.Column("region_code", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("assets", "region_code")
    op.drop_column("assets", "city")
    op.drop_column("assets", "province")
    op.drop_index(op.f("ix_region_disposal_coefficients_city"), table_name="region_disposal_coefficients")
    op.drop_index(op.f("ix_region_disposal_coefficients_province"), table_name="region_disposal_coefficients")
    op.drop_table("region_disposal_coefficients")
    op.drop_index(op.f("ix_brand_retention_profiles_vehicle_type"), table_name="brand_retention_profiles")
    op.drop_table("brand_retention_profiles")
