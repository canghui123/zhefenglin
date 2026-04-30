"""Repository helpers for customer data imports."""

from typing import Any, Optional

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from db.models.data_import import DataImportBatch, DataImportRow


ACTIVE_SOURCE_STATUS = "active"
ARCHIVED_SOURCE_STATUS = "archived"
PARSED_STATUS = "parsed"
DELETED_STATUS = "deleted"
UNSET = object()


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
    include_deleted: bool = False,
) -> list[DataImportBatch]:
    stmt = (
        select(DataImportBatch)
        .where(DataImportBatch.tenant_id == tenant_id)
        .order_by(DataImportBatch.created_at.desc(), DataImportBatch.id.desc())
        .limit(limit)
    )
    if not include_deleted:
        stmt = stmt.where(DataImportBatch.status != DELETED_STATUS)
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
        .where(DataImportBatch.status != DELETED_STATUS)
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
        .where(DataImportBatch.status != DELETED_STATUS)
        .values(status=ACTIVE_SOURCE_STATUS)
    )
    session.flush()
    return int(result.rowcount or 0)


def get_batch_by_id(
    session: Session,
    batch_id: int,
    *,
    tenant_id: int,
    include_deleted: bool = False,
) -> Optional[DataImportBatch]:
    stmt = (
        select(DataImportBatch)
        .where(DataImportBatch.id == batch_id)
        .where(DataImportBatch.tenant_id == tenant_id)
    )
    if not include_deleted:
        stmt = stmt.where(DataImportBatch.status != DELETED_STATUS)
    return session.scalars(stmt).first()


def update_batch_metadata(
    session: Session,
    batch: DataImportBatch,
    *,
    filename: Any = UNSET,
    source_system: Any = UNSET,
) -> DataImportBatch:
    if filename is not UNSET:
        batch.filename = filename
    if source_system is not UNSET:
        batch.source_system = source_system
    session.flush()
    return batch


def mark_batch_deleted(session: Session, batch: DataImportBatch) -> DataImportBatch:
    batch.status = DELETED_STATUS
    session.flush()
    return batch


def _row_list_conditions(
    *,
    status: Optional[str] = None,
    q: Optional[str] = None,
    amount_filter: Optional[str] = None,
) -> list:
    conditions = []
    if status:
        conditions.append(DataImportRow.row_status == status)
    if q:
        needle = f"%{q.strip()}%"
        conditions.append(
            or_(
                DataImportRow.asset_identifier.ilike(needle),
                DataImportRow.contract_number.ilike(needle),
                DataImportRow.debtor_name.ilike(needle),
                DataImportRow.car_description.ilike(needle),
                DataImportRow.vin.ilike(needle),
                DataImportRow.license_plate.ilike(needle),
                DataImportRow.province.ilike(needle),
                DataImportRow.city.ilike(needle),
                DataImportRow.raw_json.ilike(needle),
                DataImportRow.normalized_json.ilike(needle),
            )
        )
    analyzable_condition = or_(
        func.coalesce(DataImportRow.loan_principal, 0) > 0,
        func.coalesce(DataImportRow.overdue_amount, 0) > 0,
        func.coalesce(DataImportRow.vehicle_value, 0) > 0,
    )
    if amount_filter == "analyzable":
        conditions.append(analyzable_condition)
    elif amount_filter == "missing_amount":
        conditions.append(~analyzable_condition)
    return conditions


def list_rows_page(
    session: Session,
    *,
    batch_id: int,
    status: Optional[str] = None,
    q: Optional[str] = None,
    amount_filter: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[DataImportRow], int]:
    conditions = _row_list_conditions(
        status=status,
        q=q,
        amount_filter=amount_filter,
    )
    count_stmt = (
        select(func.count())
        .select_from(DataImportRow)
        .where(DataImportRow.batch_id == batch_id)
        .where(*conditions)
    )
    total = int(session.scalar(count_stmt) or 0)
    stmt = (
        select(DataImportRow)
        .where(DataImportRow.batch_id == batch_id)
        .where(*conditions)
        .order_by(DataImportRow.row_number.asc(), DataImportRow.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(stmt).all()), total


def list_rows(
    session: Session,
    *,
    batch_id: int,
    status: Optional[str] = None,
    limit: int = 200,
) -> list[DataImportRow]:
    rows, _ = list_rows_page(
        session,
        batch_id=batch_id,
        status=status,
        limit=limit,
    )
    return rows


def get_row_by_id(
    session: Session,
    row_id: int,
    *,
    tenant_id: int,
) -> Optional[DataImportRow]:
    stmt = (
        select(DataImportRow)
        .join(DataImportBatch, DataImportBatch.id == DataImportRow.batch_id)
        .where(DataImportRow.id == row_id)
        .where(DataImportBatch.tenant_id == tenant_id)
        .where(DataImportBatch.status != DELETED_STATUS)
    )
    return session.scalars(stmt).first()


def recalculate_batch_counts(session: Session, batch: DataImportBatch) -> DataImportBatch:
    statuses = session.scalars(
        select(DataImportRow.row_status).where(DataImportRow.batch_id == batch.id)
    ).all()
    batch.total_rows = len(statuses)
    batch.success_rows = sum(1 for status in statuses if status == "valid")
    batch.error_rows = batch.total_rows - batch.success_rows
    session.flush()
    return batch


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
