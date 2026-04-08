"""High-level authentication operations.

This is the only place that knows how to combine user lookup, password
verification, JWT issuance, and session persistence. The HTTP layer
(`api/auth.py`) and the request dependency (`dependencies/auth.py`) call
into here so the rules stay in one place.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from db.models.user import User
from repositories import user_repo
from services.password_service import verify_password
from services.jwt_service import (
    JWTError,
    access_token_expiry,
    decode_access_token,
    encode_access_token,
)


class AuthError(Exception):
    """Authentication failed (bad credentials, expired/revoked session, etc.)."""


@dataclass
class IssuedSession:
    user: User
    access_token: str
    expires_at: datetime
    token_jti: str


def authenticate(
    session: Session,
    *,
    email: str,
    password: str,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> IssuedSession:
    """Verify credentials, persist a session row, and mint an access token."""
    user = user_repo.get_user_by_email(session, email=email)
    if user is None or not user.is_active:
        raise AuthError("invalid_credentials")
    if not verify_password(password, user.password_hash):
        raise AuthError("invalid_credentials")

    jti = secrets.token_urlsafe(24)
    expires_at = access_token_expiry()

    token = encode_access_token(
        user_id=user.id,
        email=user.email,
        role=user.role,
        jti=jti,
    )

    user_repo.create_session(
        session,
        user_id=user.id,
        token_jti=jti,
        # Strip tzinfo before persisting — SQLAlchemy DateTime is naive.
        expires_at=expires_at.replace(tzinfo=None),
        user_agent=user_agent,
        ip_address=ip_address,
    )
    user_repo.mark_login(session, user.id)

    return IssuedSession(
        user=user,
        access_token=token,
        expires_at=expires_at,
        token_jti=jti,
    )


def resolve_session(session: Session, token: str) -> User:
    """Decode the JWT, ensure the matching session row is still active,
    and return the user. Raises AuthError on any failure."""
    try:
        payload = decode_access_token(token)
    except JWTError as exc:
        raise AuthError(f"invalid_token:{exc}") from exc

    jti = payload.get("jti")
    if not isinstance(jti, str):
        raise AuthError("missing_jti")

    sess_row = user_repo.get_active_session_by_jti(session, jti)
    if sess_row is None:
        raise AuthError("session_revoked")
    if sess_row.expires_at and sess_row.expires_at < datetime.utcnow():
        raise AuthError("session_expired")

    user = user_repo.get_user_by_id(session, sess_row.user_id)
    if user is None or not user.is_active:
        raise AuthError("user_inactive")

    return user


def revoke(session: Session, token: str) -> None:
    """Best-effort session revocation — used by `/api/auth/logout`."""
    try:
        payload = decode_access_token(token)
    except JWTError:
        return
    jti = payload.get("jti")
    if isinstance(jti, str):
        user_repo.revoke_session(session, jti)
