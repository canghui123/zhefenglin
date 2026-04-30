"""Customer data import API."""

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import get_current_user, require_role
from errors import (
    DataImportBatchNotFound,
    DataImportRowNotFound,
    InvalidFileFormat,
    ParseError,
)
from models.data_import import (
    DataImportBatchDeleteResult,
    DataImportBatchOut,
    DataImportBatchUpdate,
    DataImportRowOut,
    DataImportRowsPage,
    DataImportRowUpdate,
    DataImportUploadResult,
)
from repositories import data_import_repo
from services import audit_service  # noqa: F401
from services.data_import_service import (
    build_upload_result,
    create_import_batch,
    delete_import_batch,
    serialize_batch,
    serialize_row,
    update_import_batch_metadata,
    update_import_row,
)
from services.storage.factory import get_storage
from services.tenant_context import get_current_tenant_id


router = APIRouter(
    prefix="/api/data-import",
    tags=["客户数据接入"],
    dependencies=[Depends(get_current_user)],
)


def _extension(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower()


@router.post(
    "/upload",
    response_model=DataImportUploadResult,
    dependencies=[Depends(require_role("operator"))],
)
async def upload_customer_data(
    request: Request,
    file: UploadFile = File(...),
    source_system: Optional[str] = Form(default=None),
    import_type: str = Form(default="asset_ledger"),
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Upload a legacy-system Excel/CSV export into an auditable staging ledger."""
    filename = file.filename or "customer-data"
    ext = _extension(filename)
    if ext not in {".xlsx", ".xls", ".csv"}:
        raise InvalidFileFormat("仅支持 .xlsx、.xls 或 .csv 文件")

    content = await file.read()
    storage_key = (
        f"data_imports/tenant_{tenant_id}/"
        f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}{ext}"
    )
    content_type = file.content_type or "application/octet-stream"
    store = get_storage()
    store.put_bytes(storage_key, content, content_type=content_type)

    try:
        batch, rows, parsed = create_import_batch(
            session,
            tenant_id=tenant_id,
            created_by=user.id,
            filename=filename,
            source_system=source_system,
            import_type=import_type,
            storage_key=storage_key,
            content=content,
        )
    except ValueError as exc:
        store.delete_object(storage_key)
        raise ParseError(str(exc))
    except Exception:
        store.delete_object(storage_key)
        raise ParseError("客户数据解析失败，请检查文件格式和表头")

    out = build_upload_result(batch, rows, parsed)
    audit_service.record(
        session,
        request,
        action="data_import.upload",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="data_import_batch",
        resource_id=batch.id,
        after={
            "filename": filename,
            "import_type": import_type,
            "source_system": source_system,
            "total_rows": batch.total_rows,
            "success_rows": batch.success_rows,
            "error_rows": batch.error_rows,
        },
    )
    return out


@router.get(
    "/batches",
    response_model=list[DataImportBatchOut],
    dependencies=[Depends(require_role("operator"))],
)
async def list_batches(
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    rows = data_import_repo.list_batches(
        session,
        tenant_id=tenant_id,
        limit=limit,
    )
    return [serialize_batch(row) for row in rows]


@router.put(
    "/batches/{batch_id}",
    response_model=DataImportBatchOut,
    dependencies=[Depends(require_role("operator"))],
)
async def update_batch(
    batch_id: int,
    payload: DataImportBatchUpdate,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    batch = data_import_repo.get_batch_by_id(
        session,
        batch_id,
        tenant_id=tenant_id,
    )
    if batch is None:
        raise DataImportBatchNotFound()
    before = serialize_batch(batch).model_dump()
    try:
        updated = update_import_batch_metadata(
            session,
            batch,
            updates=payload.model_dump(
                exclude_unset=True,
            ),
        )
    except ValueError as exc:
        raise ParseError(str(exc))
    after = serialize_batch(updated).model_dump()
    audit_service.record(
        session,
        request,
        action="data_import.batch_update",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="data_import_batch",
        resource_id=batch.id,
        before=before,
        after=after,
    )
    return serialize_batch(updated)


@router.delete(
    "/batches/{batch_id}",
    response_model=DataImportBatchDeleteResult,
    dependencies=[Depends(require_role("operator"))],
)
async def delete_batch(
    batch_id: int,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    batch = data_import_repo.get_batch_by_id(
        session,
        batch_id,
        tenant_id=tenant_id,
    )
    if batch is None:
        raise DataImportBatchNotFound()
    before = serialize_batch(batch).model_dump()
    deleted = delete_import_batch(session, batch)
    audit_service.record(
        session,
        request,
        action="data_import.batch_delete",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="data_import_batch",
        resource_id=batch.id,
        before=before,
        after=serialize_batch(deleted).model_dump(),
    )
    return DataImportBatchDeleteResult(
        id=deleted.id,
        status=deleted.status,
        message="已删除导入批次，该批次不会再显示或参与组合分析",
    )


@router.get(
    "/batches/{batch_id}/rows",
    response_model=DataImportRowsPage,
    dependencies=[Depends(require_role("operator"))],
)
async def list_batch_rows(
    batch_id: int,
    status: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None, max_length=120),
    amount_filter: Optional[str] = Query(default=None, pattern="^(analyzable|missing_amount)$"),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    batch = data_import_repo.get_batch_by_id(
        session,
        batch_id,
        tenant_id=tenant_id,
    )
    if batch is None:
        raise DataImportBatchNotFound()
    rows, total = data_import_repo.list_rows_page(
        session,
        batch_id=batch_id,
        status=status,
        q=q.strip() if q else None,
        amount_filter=amount_filter,
        limit=limit,
        offset=offset,
    )
    return DataImportRowsPage(
        batch=serialize_batch(batch),
        rows=[serialize_row(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.put(
    "/rows/{row_id}",
    response_model=DataImportRowOut,
    dependencies=[Depends(require_role("operator"))],
)
async def update_row(
    row_id: int,
    payload: DataImportRowUpdate,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    row = data_import_repo.get_row_by_id(
        session,
        row_id,
        tenant_id=tenant_id,
    )
    if row is None:
        raise DataImportRowNotFound()
    before = serialize_row(row).model_dump()
    updated = update_import_row(
        session,
        row,
        updates=payload.model_dump(exclude_unset=True),
    )
    after = serialize_row(updated).model_dump()
    audit_service.record(
        session,
        request,
        action="data_import.row_update",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="data_import_row",
        resource_id=row.id,
        before=before,
        after=after,
    )
    return serialize_row(updated)
