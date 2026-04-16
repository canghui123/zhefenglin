"""Repository for plan catalogue rows."""
import json
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.plan import Plan


def get_plan_by_id(session: Session, plan_id: int) -> Optional[Plan]:
    return session.get(Plan, plan_id)


def get_plan_by_code(session: Session, code: str) -> Optional[Plan]:
    stmt = select(Plan).where(Plan.code == code).limit(1)
    return session.scalars(stmt).first()


def list_plans(session: Session, *, active_only: bool = False) -> List[Plan]:
    stmt = select(Plan).order_by(Plan.id)
    if active_only:
        stmt = stmt.where(Plan.is_active.is_(True))
    return list(session.scalars(stmt).all())


def create_plan(session: Session, **fields) -> Plan:
    row = Plan(**fields)
    session.add(row)
    session.flush()
    return row


def update_plan(session: Session, plan_id: int, **fields) -> Optional[Plan]:
    row = get_plan_by_id(session, plan_id)
    if row is None:
        return None
    for key, value in fields.items():
        setattr(row, key, value)
    session.flush()
    return row
