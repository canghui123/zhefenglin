"""Repository helpers for customer data imports."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.data_import import DataImportBatch, DataImportRow


def create_batch(
    session: Session,
    *,
    tenant_id: int,
    created_by: Optional[int],
    import_type: str,
    filename: str,
    source_system: Optional[str],
    storage_key: Optional[str],
    status: str,
    total_rows: int,
    success_rows: int,
    error_rows: int,
) -> DataImportBatch:
    row = DataImportBatch(
        tenant_id=tenant_id,
        created_by=created_by,
        import_type=import_type,
        filename=filename,
        source_system=source_system,
        storage_key=storage_key,
        status=status,
        total_rows=total_rows,
        success_rows=success_rows,
        error_rows=error_rows,
    )
    session.add(row)
    session.flush()
    return row


def create_rows(
    session: Session,
    *,
    batch_id: int,
    rows: list[dict],
) -> list[DataImportRow]:
    db_rows = [DataImportRow(batch_id=batch_id, **row) for row in rows]
    session.add_all(db_rows)
    session.flush()
    return db_rows


def list_batches(
    session: Session,
    *,
    tenant_id: int,
    limit: int = 50,
) -> list[DataImportBatch]:
    stmt = (
        select(DataImportBatch)
        .where(DataImportBatch.tenant_id == tenant_id)
        .order_by(DataImportBatch.created_at.desc(), DataImportBatch.id.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def get_batch_by_id(
    session: Session,
    batch_id: int,
    *,
    tenant_id: int,
) -> Optional[DataImportBatch]:
    stmt = (
        select(DataImportBatch)
        .where(DataImportBatch.id == batch_id)
        .where(DataImportBatch.tenant_id == tenant_id)
    )
    return session.scalars(stmt).first()


def list_rows(
    session: Session,
    *,
    batch_id: int,
    status: Optional[str] = None,
    limit: int = 200,
) -> list[DataImportRow]:
    stmt = (
        select(DataImportRow)
        .where(DataImportRow.batch_id == batch_id)
        .order_by(DataImportRow.row_number.asc(), DataImportRow.id.asc())
        .limit(limit)
    )
    if status:
        stmt = stmt.where(DataImportRow.row_status == status)
    return list(session.scalars(stmt).all())
