"""Access request 仓储层 —— 申请制内测留资。"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.access_request import AccessRequest


def create_request(
    session: Session,
    *,
    email: str,
    company: str,
    contact_name: str,
    phone: Optional[str] = None,
    scenario: Optional[str] = None,
    source: Optional[str] = None,
    terms_version: Optional[str] = None,
) -> AccessRequest:
    req = AccessRequest(
        email=email.strip().lower(),
        company=company.strip(),
        contact_name=contact_name.strip(),
        phone=(phone or "").strip() or None,
        scenario=(scenario or "").strip() or None,
        source=(source or "").strip() or None,
        terms_version=terms_version,
    )
    session.add(req)
    session.flush()
    return req


def get_latest_pending_by_email(
    session: Session, email: str
) -> Optional[AccessRequest]:
    stmt = (
        select(AccessRequest)
        .where(
            AccessRequest.email == email.strip().lower(),
            AccessRequest.status == "pending",
        )
        .order_by(AccessRequest.created_at.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def list_pending(session: Session, limit: int = 100) -> list[AccessRequest]:
    stmt = (
        select(AccessRequest)
        .where(AccessRequest.status == "pending")
        .order_by(AccessRequest.created_at.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())
