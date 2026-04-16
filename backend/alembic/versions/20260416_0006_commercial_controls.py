"""commercial controls platform tables

Revision ID: 20260416_0006
Revises: 20260410_0005
Create Date: 2026-04-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260416_0006"
down_revision: Union[str, None] = "20260410_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("billing_cycle_supported", sa.String(length=64), nullable=False),
        sa.Column("monthly_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("yearly_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column("setup_fee", sa.Float(), nullable=False, server_default="0"),
        sa.Column("private_deploy_fee", sa.Float(), nullable=False, server_default="0"),
        sa.Column("seat_limit", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("included_vin_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "included_condition_pricing_points",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("included_ai_reports", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "included_asset_packages", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("included_sandbox_runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overage_vin_unit_price", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "overage_condition_pricing_unit_price",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("feature_flags_json", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_plans_code"),
    )
    op.create_index("ix_plans_code", "plans", ["code"], unique=False)

    op.create_table(
        "tenant_subscriptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("custom_pricing_json", sa.Text(), nullable=True),
        sa.Column("monthly_budget_limit", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "alert_threshold_percent", sa.Float(), nullable=False, server_default="80"
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenant_subscriptions_tenant_id", "tenant_subscriptions", ["tenant_id"], unique=False)
    op.create_index("ix_tenant_subscriptions_status", "tenant_subscriptions", ["status"], unique=False)

    op.create_table(
        "feature_entitlements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False, server_default="plan"),
        sa.Column("plan_id", sa.Integer(), nullable=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("feature_key", sa.String(length=128), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feature_entitlements_tenant_id", "feature_entitlements", ["tenant_id"], unique=False)
    op.create_index("ix_feature_entitlements_feature_key", "feature_entitlements", ["feature_key"], unique=False)

    op.create_table(
        "usage_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("module", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False, server_default="1"),
        sa.Column("unit_cost_internal", sa.Float(), nullable=False, server_default="0"),
        sa.Column("unit_price_external", sa.Float(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_total", sa.Float(), nullable=False, server_default="0"),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("related_object_type", sa.String(length=64), nullable=True),
        sa.Column("related_object_id", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_usage_events_tenant_id", "usage_events", ["tenant_id"], unique=False)
    op.create_index("ix_usage_events_module", "usage_events", ["module"], unique=False)
    op.create_index("ix_usage_events_created_at", "usage_events", ["created_at"], unique=False)
    op.create_index("ix_usage_events_request_id", "usage_events", ["request_id"], unique=False)

    op.create_table(
        "cost_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("vin_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("condition_pricing_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("che300_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("estimated_revenue", sa.Float(), nullable=False, server_default="0"),
        sa.Column("estimated_gross_profit", sa.Float(), nullable=False, server_default="0"),
        sa.Column("extra_metrics_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cost_snapshots_tenant_id", "cost_snapshots", ["tenant_id"], unique=False)
    op.create_index("ix_cost_snapshots_month", "cost_snapshots", ["month"], unique=False)

    op.create_table(
        "model_routing_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False, server_default="global"),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("preferred_model", sa.String(length=128), nullable=False),
        sa.Column("fallback_model", sa.String(length=128), nullable=True),
        sa.Column("allow_batch", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_search", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_high_cost_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("prompt_version", sa.String(length=64), nullable=False, server_default="v1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_routing_rules_scope", "model_routing_rules", ["scope"], unique=False)
    op.create_index("ix_model_routing_rules_tenant_id", "model_routing_rules", ["tenant_id"], unique=False)
    op.create_index("ix_model_routing_rules_task_type", "model_routing_rules", ["task_type"], unique=False)

    op.create_table(
        "valuation_trigger_rules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False, server_default="global"),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("trigger_type", sa.String(length=64), nullable=False),
        sa.Column("trigger_config_json", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_valuation_trigger_rules_scope", "valuation_trigger_rules", ["scope"], unique=False)
    op.create_index("ix_valuation_trigger_rules_tenant_id", "valuation_trigger_rules", ["tenant_id"], unique=False)

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("applicant_user_id", sa.Integer(), nullable=False),
        sa.Column("approver_user_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("related_object_type", sa.String(length=64), nullable=True),
        sa.Column("related_object_id", sa.String(length=64), nullable=True),
        sa.Column("estimated_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("actual_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["applicant_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approver_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_requests_tenant_id", "approval_requests", ["tenant_id"], unique=False)
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_approval_requests_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_tenant_id", table_name="approval_requests")
    op.drop_table("approval_requests")

    op.drop_index("ix_valuation_trigger_rules_tenant_id", table_name="valuation_trigger_rules")
    op.drop_index("ix_valuation_trigger_rules_scope", table_name="valuation_trigger_rules")
    op.drop_table("valuation_trigger_rules")

    op.drop_index("ix_model_routing_rules_task_type", table_name="model_routing_rules")
    op.drop_index("ix_model_routing_rules_tenant_id", table_name="model_routing_rules")
    op.drop_index("ix_model_routing_rules_scope", table_name="model_routing_rules")
    op.drop_table("model_routing_rules")

    op.drop_index("ix_cost_snapshots_month", table_name="cost_snapshots")
    op.drop_index("ix_cost_snapshots_tenant_id", table_name="cost_snapshots")
    op.drop_table("cost_snapshots")

    op.drop_index("ix_usage_events_request_id", table_name="usage_events")
    op.drop_index("ix_usage_events_created_at", table_name="usage_events")
    op.drop_index("ix_usage_events_module", table_name="usage_events")
    op.drop_index("ix_usage_events_tenant_id", table_name="usage_events")
    op.drop_table("usage_events")

    op.drop_index("ix_feature_entitlements_feature_key", table_name="feature_entitlements")
    op.drop_index("ix_feature_entitlements_tenant_id", table_name="feature_entitlements")
    op.drop_table("feature_entitlements")

    op.drop_index("ix_tenant_subscriptions_status", table_name="tenant_subscriptions")
    op.drop_index("ix_tenant_subscriptions_tenant_id", table_name="tenant_subscriptions")
    op.drop_table("tenant_subscriptions")

    op.drop_index("ix_plans_code", table_name="plans")
    op.drop_table("plans")
