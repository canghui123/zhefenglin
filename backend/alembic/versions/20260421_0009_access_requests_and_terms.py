"""access requests + user terms columns

Revision ID: 20260421_0009
Revises: 20260417_0008
Create Date: 2026-04-21

MVP 合规补丁：
- users 表增加 terms_accepted_at / terms_version，记录用户同意时间与版本
- 新建 access_requests 表，承接"申请制内测"留资
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260421_0009"
down_revision: Union[str, None] = "20260417_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users: terms fields -----------------------------------------------
    op.add_column(
        "users",
        sa.Column("terms_accepted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("terms_version", sa.String(length=32), nullable=True),
    )

    # --- access_requests ---------------------------------------------------
    op.create_table(
        "access_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("contact_name", sa.String(length=64), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("scenario", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("terms_version", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'contacted')",
            name="ck_access_requests_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_access_requests"),
    )
    op.create_index(
        "ix_access_requests_email", "access_requests", ["email"], unique=False
    )
    op.create_index(
        "ix_access_requests_status_created_at",
        "access_requests",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_access_requests_status_created_at", table_name="access_requests")
    op.drop_index("ix_access_requests_email", table_name="access_requests")
    op.drop_table("access_requests")
    op.drop_column("users", "terms_version")
    op.drop_column("users", "terms_accepted_at")
