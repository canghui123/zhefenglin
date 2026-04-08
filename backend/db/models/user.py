"""User account ORM model.

For Task 5 we keep RBAC simple: a single `role` column on `users`. The
allowed values are enumerated in `db.models.role.ROLES`. A separate
`roles` table can be introduced later if we need per-tenant role
assignment or custom permissions.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
