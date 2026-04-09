"""tenants, memberships, audit_logs + tenant_id on business tables

Revision ID: 20260408_0003
Revises: 20260408_0002
Create Date: 2026-04-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260408_0003"
down_revision: Union[str, None] = "20260408_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- tenants ----
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("notes", sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_tenants_code"),
    )
    op.create_index("ix_tenants_code", "tenants", ["code"], unique=False)

    # Seed a default tenant so existing rows have something to point at and
    # the bootstrap admin script doesn't need a special-case branch.
    op.execute(
        "INSERT INTO tenants (id, code, name, is_active) "
        "VALUES (1, 'default', 'Default Tenant', TRUE)"
    )
    # Postgres needs the sequence advanced past the manually-inserted id.
    op.execute(
        "SELECT setval(pg_get_serial_sequence('tenants', 'id'), "
        "(SELECT MAX(id) FROM tenants))"
    )

    # ---- memberships ----
    op.create_table(
        "memberships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="viewer"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_memberships_user_tenant"),
    )
    op.create_index(
        "ix_memberships_user_id", "memberships", ["user_id"], unique=False
    )
    op.create_index(
        "ix_memberships_tenant_id", "memberships", ["tenant_id"], unique=False
    )

    # ---- audit_logs ----
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="success"),
        sa.Column("before_json", sa.Text(), nullable=True),
        sa.Column("after_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"], unique=False)
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"], unique=False)
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"], unique=False)
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"], unique=False)

    # ---- users.default_tenant_id ----
    op.add_column(
        "users",
        sa.Column("default_tenant_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_default_tenant",
        "users",
        "tenants",
        ["default_tenant_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ---- asset_packages.tenant_id / created_by ----
    op.add_column(
        "asset_packages",
        sa.Column("tenant_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "asset_packages",
        sa.Column("created_by", sa.Integer(), nullable=True),
    )
    op.execute("UPDATE asset_packages SET tenant_id = 1 WHERE tenant_id IS NULL")
    op.alter_column("asset_packages", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_asset_packages_tenant",
        "asset_packages",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_asset_packages_created_by",
        "asset_packages",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_asset_packages_tenant_id", "asset_packages", ["tenant_id"], unique=False
    )

    # ---- sandbox_results.tenant_id / created_by ----
    op.add_column(
        "sandbox_results",
        sa.Column("tenant_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "sandbox_results",
        sa.Column("created_by", sa.Integer(), nullable=True),
    )
    op.execute("UPDATE sandbox_results SET tenant_id = 1 WHERE tenant_id IS NULL")
    op.alter_column("sandbox_results", "tenant_id", nullable=False)
    op.create_foreign_key(
        "fk_sandbox_results_tenant",
        "sandbox_results",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_sandbox_results_created_by",
        "sandbox_results",
        "users",
        ["created_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_sandbox_results_tenant_id", "sandbox_results", ["tenant_id"], unique=False
    )

    # ---- portfolio_snapshots.tenant_id (nullable — still mock-only) ----
    op.add_column(
        "portfolio_snapshots",
        sa.Column("tenant_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_portfolio_snapshots_tenant",
        "portfolio_snapshots",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_portfolio_snapshots_tenant_id",
        "portfolio_snapshots",
        ["tenant_id"],
        unique=False,
    )

    # ---- asset_segments.tenant_id ----
    op.add_column(
        "asset_segments",
        sa.Column("tenant_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_asset_segments_tenant",
        "asset_segments",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_asset_segments_tenant_id", "asset_segments", ["tenant_id"], unique=False
    )

    # ---- management_goals.tenant_id ----
    op.add_column(
        "management_goals",
        sa.Column("tenant_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_management_goals_tenant",
        "management_goals",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_management_goals_tenant_id", "management_goals", ["tenant_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_management_goals_tenant_id", table_name="management_goals")
    op.drop_constraint("fk_management_goals_tenant", "management_goals", type_="foreignkey")
    op.drop_column("management_goals", "tenant_id")

    op.drop_index("ix_asset_segments_tenant_id", table_name="asset_segments")
    op.drop_constraint("fk_asset_segments_tenant", "asset_segments", type_="foreignkey")
    op.drop_column("asset_segments", "tenant_id")

    op.drop_index("ix_portfolio_snapshots_tenant_id", table_name="portfolio_snapshots")
    op.drop_constraint(
        "fk_portfolio_snapshots_tenant", "portfolio_snapshots", type_="foreignkey"
    )
    op.drop_column("portfolio_snapshots", "tenant_id")

    op.drop_index("ix_sandbox_results_tenant_id", table_name="sandbox_results")
    op.drop_constraint("fk_sandbox_results_created_by", "sandbox_results", type_="foreignkey")
    op.drop_constraint("fk_sandbox_results_tenant", "sandbox_results", type_="foreignkey")
    op.drop_column("sandbox_results", "created_by")
    op.drop_column("sandbox_results", "tenant_id")

    op.drop_index("ix_asset_packages_tenant_id", table_name="asset_packages")
    op.drop_constraint("fk_asset_packages_created_by", "asset_packages", type_="foreignkey")
    op.drop_constraint("fk_asset_packages_tenant", "asset_packages", type_="foreignkey")
    op.drop_column("asset_packages", "created_by")
    op.drop_column("asset_packages", "tenant_id")

    op.drop_constraint("fk_users_default_tenant", "users", type_="foreignkey")
    op.drop_column("users", "default_tenant_id")

    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_request_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_user_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_id", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_memberships_tenant_id", table_name="memberships")
    op.drop_index("ix_memberships_user_id", table_name="memberships")
    op.drop_table("memberships")

    op.drop_index("ix_tenants_code", table_name="tenants")
    op.drop_table("tenants")
