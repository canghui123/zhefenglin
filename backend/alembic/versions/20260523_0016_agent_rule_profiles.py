"""Agent rule settings profiles.

Revision ID: 20260523_0016
Revises: 20260523_0015
Create Date: 2026-05-23
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260523_0016"
down_revision: Union[str, None] = "20260523_0015"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.drop_constraint("uq_agent_rule_settings_tenant", "agent_rule_settings", type_="unique")
    op.add_column(
        "agent_rule_settings",
        sa.Column("agent_type", sa.String(length=64), server_default="global", nullable=False),
    )
    op.add_column(
        "agent_rule_settings",
        sa.Column("scenario", sa.String(length=64), server_default="default", nullable=False),
    )
    op.add_column(
        "agent_rule_settings",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "agent_rule_settings",
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.create_index(op.f("ix_agent_rule_settings_agent_type"), "agent_rule_settings", ["agent_type"])
    op.create_index(op.f("ix_agent_rule_settings_scenario"), "agent_rule_settings", ["scenario"])
    op.create_index(op.f("ix_agent_rule_settings_is_active"), "agent_rule_settings", ["is_active"])
    op.create_unique_constraint(
        "uq_agent_rule_settings_profile",
        "agent_rule_settings",
        ["tenant_id", "agent_type", "scenario", "version"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_agent_rule_settings_profile", "agent_rule_settings", type_="unique")
    op.drop_index(op.f("ix_agent_rule_settings_is_active"), table_name="agent_rule_settings")
    op.drop_index(op.f("ix_agent_rule_settings_scenario"), table_name="agent_rule_settings")
    op.drop_index(op.f("ix_agent_rule_settings_agent_type"), table_name="agent_rule_settings")
    op.drop_column("agent_rule_settings", "is_active")
    op.drop_column("agent_rule_settings", "version")
    op.drop_column("agent_rule_settings", "scenario")
    op.drop_column("agent_rule_settings", "agent_type")
    op.create_unique_constraint(
        "uq_agent_rule_settings_tenant",
        "agent_rule_settings",
        ["tenant_id"],
    )
