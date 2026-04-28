"""Repository for sandbox_results table.

All reads/writes are scoped to a tenant. See asset_package_repo for the
same pattern.
"""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.sandbox import (
    SandboxResult as SandboxResultORM,
    SandboxSimulationBatch,
    SandboxSimulationBatchItem,
)


def create_sandbox_result(
    session: Session,
    *,
    tenant_id: int,
    created_by: Optional[int] = None,
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
        tenant_id=tenant_id,
        created_by=created_by,
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


def get_sandbox_result_by_id(
    session: Session, result_id: int, *, tenant_id: int
) -> Optional[SandboxResultORM]:
    stmt = (
        select(SandboxResultORM)
        .where(SandboxResultORM.id == result_id)
        .where(SandboxResultORM.tenant_id == tenant_id)
        .limit(1)
    )
    return session.scalars(stmt).first()


def list_sandbox_results(
    session: Session, *, tenant_id: int
) -> List[SandboxResultORM]:
    stmt = (
        select(SandboxResultORM)
        .where(SandboxResultORM.tenant_id == tenant_id)
        .order_by(SandboxResultORM.created_at.desc())
    )
    return list(session.scalars(stmt).all())


def create_sandbox_batch(
    session: Session,
    *,
    tenant_id: int,
    created_by: Optional[int],
    total_rows: int,
    success_rows: int = 0,
    error_rows: int = 0,
    status: str = "completed",
) -> SandboxSimulationBatch:
    row = SandboxSimulationBatch(
        tenant_id=tenant_id,
        created_by=created_by,
        status=status,
        total_rows=total_rows,
        success_rows=success_rows,
        error_rows=error_rows,
    )
    session.add(row)
    session.flush()
    return row


def create_sandbox_batch_item(
    session: Session,
    *,
    batch_id: int,
    row_id: str,
    row_number: int,
    row_status: str,
    sandbox_result_id: Optional[int] = None,
    car_description: Optional[str] = None,
    overdue_bucket: Optional[str] = None,
    overdue_amount: Optional[float] = None,
    che300_value: Optional[float] = None,
    best_path: Optional[str] = None,
    error_message: Optional[str] = None,
    input_json: Optional[str] = None,
) -> SandboxSimulationBatchItem:
    row = SandboxSimulationBatchItem(
        batch_id=batch_id,
        sandbox_result_id=sandbox_result_id,
        row_id=row_id,
        row_number=row_number,
        row_status=row_status,
        car_description=car_description,
        overdue_bucket=overdue_bucket,
        overdue_amount=overdue_amount,
        che300_value=che300_value,
        best_path=best_path,
        error_message=error_message,
        input_json=input_json,
    )
    session.add(row)
    session.flush()
    return row


def update_sandbox_batch_counts(
    session: Session,
    batch_id: int,
    *,
    tenant_id: int,
    success_rows: int,
    error_rows: int,
    status: str = "completed",
) -> Optional[SandboxSimulationBatch]:
    row = get_sandbox_batch_by_id(session, batch_id, tenant_id=tenant_id)
    if row is None:
        return None
    row.success_rows = success_rows
    row.error_rows = error_rows
    row.status = status
    session.flush()
    return row


def list_sandbox_batches(
    session: Session,
    *,
    tenant_id: int,
    limit: int = 50,
) -> List[SandboxSimulationBatch]:
    stmt = (
        select(SandboxSimulationBatch)
        .where(SandboxSimulationBatch.tenant_id == tenant_id)
        .order_by(SandboxSimulationBatch.created_at.desc(), SandboxSimulationBatch.id.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def get_sandbox_batch_by_id(
    session: Session,
    batch_id: int,
    *,
    tenant_id: int,
) -> Optional[SandboxSimulationBatch]:
    stmt = (
        select(SandboxSimulationBatch)
        .where(SandboxSimulationBatch.id == batch_id)
        .where(SandboxSimulationBatch.tenant_id == tenant_id)
        .limit(1)
    )
    return session.scalars(stmt).first()


def list_sandbox_batch_items(
    session: Session,
    *,
    batch_id: int,
) -> List[SandboxSimulationBatchItem]:
    stmt = (
        select(SandboxSimulationBatchItem)
        .where(SandboxSimulationBatchItem.batch_id == batch_id)
        .order_by(SandboxSimulationBatchItem.row_number.asc(), SandboxSimulationBatchItem.id.asc())
    )
    return list(session.scalars(stmt).all())


def update_report_path(
    session: Session, result_id: int, *, tenant_id: int, pdf_path: str
) -> None:
    row = get_sandbox_result_by_id(session, result_id, tenant_id=tenant_id)
    if row is not None:
        row.report_pdf_path = pdf_path


def update_report_storage_key(
    session: Session,
    result_id: int,
    *,
    tenant_id: int,
    storage_key: str,
) -> None:
    row = get_sandbox_result_by_id(session, result_id, tenant_id=tenant_id)
    if row is not None:
        row.report_storage_key = storage_key
