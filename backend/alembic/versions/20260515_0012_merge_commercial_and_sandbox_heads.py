"""Merge commercial controls and sandbox batch migration histories.

Revision ID: 20260515_0012
Revises: 20260421_0009, 20260428_0011
Create Date: 2026-05-15
"""
from typing import Sequence, Union


revision: str = "20260515_0012"
down_revision: Union[str, Sequence[str], None] = (
    "20260421_0009",
    "20260428_0011",
)
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
