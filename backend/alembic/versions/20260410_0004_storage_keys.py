"""add storage_key columns for object-storage abstraction

Revision ID: 20260410_0004
Revises: 20260408_0003
Create Date: 2026-04-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260410_0004"
down_revision: Union[str, None] = "20260408_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "asset_packages",
        sa.Column("storage_key", sa.String(), nullable=True),
    )
    # Backfill: existing rows that have a local filename get the same value
    # as their storage_key so the code path is uniform.
    op.execute(
        "UPDATE asset_packages SET storage_key = upload_filename "
        "WHERE upload_filename IS NOT NULL AND storage_key IS NULL"
    )

    op.add_column(
        "sandbox_results",
        sa.Column("report_storage_key", sa.String(), nullable=True),
    )
    op.execute(
        "UPDATE sandbox_results SET report_storage_key = report_pdf_path "
        "WHERE report_pdf_path IS NOT NULL AND report_storage_key IS NULL"
    )


def downgrade() -> None:
    op.drop_column("sandbox_results", "report_storage_key")
    op.drop_column("asset_packages", "storage_key")
