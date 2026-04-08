"""Repository for sandbox_results table."""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.sandbox import SandboxResult as SandboxResultORM


def create_sandbox_result(
    session: Session,
    *,
    car_description: Optional[str],
    entry_date: Optional[str],
    overdue_amount: Optional[float],
    che300_value: Optional[float],
    daily_parking: Optional[float],
    input_json: str,
    path_a_json: str,
    path_b_json: str,
    path_c_json: str,
    path_d_json: str,
    path_e_json: str,
    recommendation: Optional[str],
    best_path: Optional[str],
) -> SandboxResultORM:
    row = SandboxResultORM(
        car_description=car_description,
        entry_date=entry_date,
        overdue_amount=overdue_amount,
        che300_value=che300_value,
        daily_parking=daily_parking,
        input_json=input_json,
        path_a_json=path_a_json,
        path_b_json=path_b_json,
        path_c_json=path_c_json,
        path_d_json=path_d_json,
        path_e_json=path_e_json,
        recommendation=recommendation,
        best_path=best_path,
    )
    session.add(row)
    session.flush()
    return row


def get_sandbox_result_by_id(session: Session, result_id: int) -> Optional[SandboxResultORM]:
    return session.get(SandboxResultORM, result_id)


def list_sandbox_results(session: Session) -> List[SandboxResultORM]:
    stmt = select(SandboxResultORM).order_by(SandboxResultORM.created_at.desc())
    return list(session.scalars(stmt).all())


def update_report_path(session: Session, result_id: int, pdf_path: str) -> None:
    row = session.get(SandboxResultORM, result_id)
    if row is not None:
        row.report_pdf_path = pdf_path
