"""Repository helpers for customer data imports."""

from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from db.models.data_import import DataImportBatch, DataImportRow


ACTIVE_SOURCE_STATUS = "active"
ARCHIVED_SOURCE_STATUS = "archived"
PARSED_STATUS = "parsed"


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


def get_latest_batch_with_rows(
    session: Session,
    *,
    tenant_id: int,
    import_type: Optional[str] = None,
) -> Optional[DataImportBatch]:
    stmt = (
        select(DataImportBatch)
        .where(DataImportBatch.tenant_id == tenant_id)
        .where(DataImportBatch.success_rows > 0)
        .where(DataImportBatch.status == PARSED_STATUS)
        .order_by(DataImportBatch.created_at.desc(), DataImportBatch.id.desc())
        .limit(1)
    )
    if import_type:
        stmt = stmt.where(DataImportBatch.import_type == import_type)
    return session.scalars(stmt).first()


def list_active_batches_with_rows(
    session: Session,
    *,
    tenant_id: int,
    import_type: str = "asset_ledger",
) -> list[DataImportBatch]:
    stmt = (
        select(DataImportBatch)
        .where(DataImportBatch.tenant_id == tenant_id)
        .where(DataImportBatch.import_type == import_type)
        .where(DataImportBatch.success_rows > 0)
        .where(DataImportBatch.status == ACTIVE_SOURCE_STATUS)
        .order_by(DataImportBatch.created_at.desc(), DataImportBatch.id.desc())
    )
    return list(session.scalars(stmt).all())


def has_any_batch(
    session: Session,
    *,
    tenant_id: int,
    import_type: Optional[str] = None,
) -> bool:
    stmt = (
        select(DataImportBatch.id)
        .where(DataImportBatch.tenant_id == tenant_id)
        .limit(1)
    )
    if import_type:
        stmt = stmt.where(DataImportBatch.import_type == import_type)
    return session.scalars(stmt).first() is not None


def archive_active_batches(
    session: Session,
    *,
    tenant_id: int,
    import_type: str = "asset_ledger",
) -> int:
    result = session.execute(
        update(DataImportBatch)
        .where(DataImportBatch.tenant_id == tenant_id)
        .where(DataImportBatch.import_type == import_type)
        .where(DataImportBatch.status.in_([ACTIVE_SOURCE_STATUS, PARSED_STATUS]))
        .values(status=ARCHIVED_SOURCE_STATUS)
    )
    session.flush()
    return int(result.rowcount or 0)


def list_source_batches_by_ids(
    session: Session,
    *,
    tenant_id: int,
    batch_ids: list[int],
    import_type: str = "asset_ledger",
) -> list[DataImportBatch]:
    if not batch_ids:
        return []
    stmt = (
        select(DataImportBatch)
        .where(DataImportBatch.tenant_id == tenant_id)
        .where(DataImportBatch.import_type == import_type)
        .where(DataImportBatch.success_rows > 0)
        .where(DataImportBatch.id.in_(batch_ids))
        .order_by(DataImportBatch.created_at.desc(), DataImportBatch.id.desc())
    )
    return list(session.scalars(stmt).all())


def activate_batches_as_source(
    session: Session,
    *,
    tenant_id: int,
    batch_ids: list[int],
    import_type: str = "asset_ledger",
) -> int:
    if not batch_ids:
        return 0
    archive_active_batches(session, tenant_id=tenant_id, import_type=import_type)
    result = session.execute(
        update(DataImportBatch)
        .where(DataImportBatch.tenant_id == tenant_id)
        .where(DataImportBatch.import_type == import_type)
        .where(DataImportBatch.id.in_(batch_ids))
        .values(status=ACTIVE_SOURCE_STATUS)
    )
    session.flush()
    return int(result.rowcount or 0)


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


def list_valid_rows_for_batch(
    session: Session,
    *,
    batch_id: int,
    limit: int = 10000,
) -> list[DataImportRow]:
    stmt = (
        select(DataImportRow)
        .where(DataImportRow.batch_id == batch_id)
        .where(DataImportRow.row_status == "valid")
        .order_by(DataImportRow.row_number.asc(), DataImportRow.id.asc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())
