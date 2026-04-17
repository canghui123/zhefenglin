"""approval request consumption tracking

Revision ID: 20260417_0007
Revises: 20260416_0006
Create Date: 2026-04-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260417_0007"
down_revision: Union[str, None] = "20260416_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("approval_requests", sa.Column("consumed_at", sa.DateTime(), nullable=True))
    op.add_column(
        "approval_requests",
        sa.Column("consumed_request_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_approval_requests_consumed_request_id",
        "approval_requests",
        ["consumed_request_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_approval_requests_consumed_request_id",
        table_name="approval_requests",
    )
    op.drop_column("approval_requests", "consumed_request_id")
    op.drop_column("approval_requests", "consumed_at")
