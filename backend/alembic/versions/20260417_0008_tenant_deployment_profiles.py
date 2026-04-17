"""tenant deployment profiles

Revision ID: 20260417_0008
Revises: 20260417_0007
Create Date: 2026-04-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260417_0008"
down_revision: Union[str, None] = "20260417_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_deployment_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("deployment_mode", sa.String(length=32), nullable=False, server_default="saas_dedicated"),
        sa.Column("delivery_status", sa.String(length=32), nullable=False, server_default="planning"),
        sa.Column("access_domain", sa.String(length=255), nullable=True),
        sa.Column("sso_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sso_provider", sa.String(length=64), nullable=True),
        sa.Column("sso_login_url", sa.String(length=512), nullable=True),
        sa.Column("storage_mode", sa.String(length=32), nullable=False, server_default="platform_managed"),
        sa.Column("backup_level", sa.String(length=32), nullable=False, server_default="standard"),
        sa.Column("environment_notes", sa.Text(), nullable=True),
        sa.Column("handover_notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_tenant_deployment_profiles_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name="fk_tenant_deployment_profiles_created_by",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name="fk_tenant_deployment_profiles_updated_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tenant_deployment_profiles"),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_deployment_profiles_tenant_id"),
    )
    op.create_index(
        "ix_tenant_deployment_profiles_tenant_id",
        "tenant_deployment_profiles",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_tenant_deployment_profiles_tenant_id",
        table_name="tenant_deployment_profiles",
    )
    op.drop_table("tenant_deployment_profiles")
