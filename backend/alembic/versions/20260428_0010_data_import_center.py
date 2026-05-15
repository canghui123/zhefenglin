"""Customer data import staging center.

Revision ID: 20260428_0010
Revises: 20260427_0009
Create Date: 2026-04-28
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260428_0010"
down_revision: Union[str, None] = "20260427_0009"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "data_import_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("import_type", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("source_system", sa.String(length=120), nullable=True),
        sa.Column("storage_key", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("success_rows", sa.Integer(), nullable=False),
        sa.Column("error_rows", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_data_import_batches_tenant_id"), "data_import_batches", ["tenant_id"])
    op.create_index(op.f("ix_data_import_batches_created_by"), "data_import_batches", ["created_by"])
    op.create_index(op.f("ix_data_import_batches_import_type"), "data_import_batches", ["import_type"])
    op.create_index(op.f("ix_data_import_batches_status"), "data_import_batches", ["status"])
    op.create_index(op.f("ix_data_import_batches_created_at"), "data_import_batches", ["created_at"])

    op.create_table(
        "data_import_rows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("row_status", sa.String(length=32), nullable=False),
        sa.Column("asset_identifier", sa.String(length=120), nullable=True),
        sa.Column("contract_number", sa.String(length=120), nullable=True),
        sa.Column("debtor_name", sa.String(length=120), nullable=True),
        sa.Column("car_description", sa.String(length=255), nullable=True),
        sa.Column("vin", sa.String(length=80), nullable=True),
        sa.Column("license_plate", sa.String(length=40), nullable=True),
        sa.Column("province", sa.String(length=64), nullable=True),
        sa.Column("city", sa.String(length=64), nullable=True),
        sa.Column("overdue_bucket", sa.String(length=64), nullable=True),
        sa.Column("overdue_days", sa.Integer(), nullable=True),
        sa.Column("overdue_amount", sa.Integer(), nullable=True),
        sa.Column("loan_principal", sa.Integer(), nullable=True),
        sa.Column("vehicle_value", sa.Integer(), nullable=True),
        sa.Column("recovered_status", sa.String(length=64), nullable=True),
        sa.Column("gps_last_seen", sa.String(length=120), nullable=True),
        sa.Column("errors_json", sa.Text(), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=False),
        sa.Column("normalized_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["data_import_batches.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_data_import_rows_batch_id"), "data_import_rows", ["batch_id"])
    op.create_index(op.f("ix_data_import_rows_row_status"), "data_import_rows", ["row_status"])
    op.create_index(op.f("ix_data_import_rows_asset_identifier"), "data_import_rows", ["asset_identifier"])
    op.create_index(op.f("ix_data_import_rows_contract_number"), "data_import_rows", ["contract_number"])
    op.create_index(op.f("ix_data_import_rows_vin"), "data_import_rows", ["vin"])
    op.create_index(op.f("ix_data_import_rows_license_plate"), "data_import_rows", ["license_plate"])
    op.create_index(op.f("ix_data_import_rows_province"), "data_import_rows", ["province"])
    op.create_index(op.f("ix_data_import_rows_city"), "data_import_rows", ["city"])
    op.create_index(op.f("ix_data_import_rows_overdue_bucket"), "data_import_rows", ["overdue_bucket"])
    op.create_index(op.f("ix_data_import_rows_recovered_status"), "data_import_rows", ["recovered_status"])
    op.create_index(op.f("ix_data_import_rows_created_at"), "data_import_rows", ["created_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_data_import_rows_created_at"), table_name="data_import_rows")
    op.drop_index(op.f("ix_data_import_rows_recovered_status"), table_name="data_import_rows")
    op.drop_index(op.f("ix_data_import_rows_overdue_bucket"), table_name="data_import_rows")
    op.drop_index(op.f("ix_data_import_rows_city"), table_name="data_import_rows")
    op.drop_index(op.f("ix_data_import_rows_province"), table_name="data_import_rows")
    op.drop_index(op.f("ix_data_import_rows_license_plate"), table_name="data_import_rows")
    op.drop_index(op.f("ix_data_import_rows_vin"), table_name="data_import_rows")
    op.drop_index(op.f("ix_data_import_rows_contract_number"), table_name="data_import_rows")
    op.drop_index(op.f("ix_data_import_rows_asset_identifier"), table_name="data_import_rows")
    op.drop_index(op.f("ix_data_import_rows_row_status"), table_name="data_import_rows")
    op.drop_index(op.f("ix_data_import_rows_batch_id"), table_name="data_import_rows")
    op.drop_table("data_import_rows")
    op.drop_index(op.f("ix_data_import_batches_created_at"), table_name="data_import_batches")
    op.drop_index(op.f("ix_data_import_batches_status"), table_name="data_import_batches")
    op.drop_index(op.f("ix_data_import_batches_import_type"), table_name="data_import_batches")
    op.drop_index(op.f("ix_data_import_batches_created_by"), table_name="data_import_batches")
    op.drop_index(op.f("ix_data_import_batches_tenant_id"), table_name="data_import_batches")
    op.drop_table("data_import_batches")
