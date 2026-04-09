"""Repository for users and user_sessions."""
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.user import User
from db.models.user_session import UserSession


# ---------- users ----------

def create_user(
    session: Session,
    *,
    email: str,
    password_hash: str,
    role: str = "viewer",
    display_name: Optional[str] = None,
) -> User:
    user = User(
        email=email,
        password_hash=password_hash,
        role=role,
        display_name=display_name,
    )
    session.add(user)
    session.flush()
    return user


def get_user_by_email(session: Session, email: str) -> Optional[User]:
    stmt = select(User).where(User.email == email).limit(1)
    return session.scalars(stmt).first()


def get_user_by_id(session: Session, user_id: int) -> Optional[User]:
    return session.get(User, user_id)


def mark_login(session: Session, user_id: int) -> None:
    user = session.get(User, user_id)
    if user is not None:
        user.last_login_at = datetime.utcnow()


def set_default_tenant(session: Session, user_id: int, tenant_id: int) -> None:
    user = session.get(User, user_id)
    if user is not None:
        user.default_tenant_id = tenant_id


# ---------- sessions ----------

def create_session(
    session: Session,
    *,
    user_id: int,
    token_jti: str,
    expires_at: datetime,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> UserSession:
    row = UserSession(
        user_id=user_id,
        token_jti=token_jti,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    session.add(row)
    session.flush()
    return row


def get_active_session_by_jti(
    session: Session, token_jti: str
) -> Optional[UserSession]:
    stmt = (
        select(UserSession)
        .where(UserSession.token_jti == token_jti)
        .where(UserSession.revoked_at.is_(None))
        .limit(1)
    )
    return session.scalars(stmt).first()


def revoke_session(session: Session, token_jti: str) -> None:
    row = session.scalars(
        select(UserSession).where(UserSession.token_jti == token_jti).limit(1)
    ).first()
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.utcnow()
