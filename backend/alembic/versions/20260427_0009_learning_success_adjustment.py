"""Track applied success-probability learning adjustments.

Revision ID: 20260427_0009
Revises: 20260427_0008
Create Date: 2026-04-27
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260427_0009"
down_revision: Union[str, None] = "20260427_0008"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "model_learning_runs",
        sa.Column(
            "success_adjustment_applied",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("model_learning_runs", "success_adjustment_applied")
