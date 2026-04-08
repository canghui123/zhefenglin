"""Server-side session record for issued JWTs.

We persist sessions so admins can revoke active logins and so the
`/api/auth/me` endpoint can verify the token has not been logged out.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_jti: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
