"""Model feedback and learning-loop API."""

import os

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import get_current_user, require_role
from errors import InvalidFileFormat, ParseError
from models.model_feedback import (
    DisposalOutcomeCreate,
    DisposalOutcomeOut,
    ModelFeedbackBatchImportResult,
    ModelFeedbackSummary,
    ModelLearningRunCreate,
    ModelLearningRunOut,
)
from repositories import model_feedback_repo
from services import audit_service  # noqa: F401
from services.model_feedback_service import (
    compute_feedback_summary,
    import_feedback_batch_and_run_learning,
    record_disposal_outcome,
    run_learning_cycle,
    serialize_disposal_outcome,
    serialize_learning_run,
)
from services.tenant_context import get_current_tenant_id


router = APIRouter(
    prefix="/api/model-feedback",
    tags=["模型复盘"],
    dependencies=[Depends(get_current_user)],
)


def _extension(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower()


@router.get(
    "/outcomes",
    response_model=list[DisposalOutcomeOut],
    dependencies=[Depends(require_role("operator"))],
)
async def list_outcomes(
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    rows = model_feedback_repo.list_disposal_outcomes(
        session,
        tenant_id=tenant_id,
        limit=limit,
    )
    return [serialize_disposal_outcome(row) for row in rows]


@router.post(
    "/outcomes",
    response_model=DisposalOutcomeOut,
    dependencies=[Depends(require_role("operator"))],
)
async def create_outcome(
    req: DisposalOutcomeCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    row = record_disposal_outcome(
        session,
        tenant_id=tenant_id,
        created_by=user.id,
        req=req,
    )
    out = serialize_disposal_outcome(row)
    audit_service.record(
        session,
        request,
        action="model_feedback.outcome_create",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="disposal_outcome",
        resource_id=row.id,
        after=out.model_dump(),
    )
    return out


@router.post(
    "/outcomes/import",
    response_model=ModelFeedbackBatchImportResult,
    dependencies=[Depends(require_role("manager"))],
)
async def import_outcomes(
    request: Request,
    file: UploadFile = File(...),
    apply_region_adjustments: bool = Form(default=False),
    apply_success_adjustment: bool = Form(default=False),
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    """Import disposal outcome feedback rows and immediately create a learning run."""
    filename = file.filename or "model-feedback"
    if _extension(filename) not in {".xlsx", ".xls", ".csv"}:
        raise InvalidFileFormat("仅支持 .xlsx、.xls 或 .csv 文件")

    content = await file.read()
    try:
        parsed, created_rows, learning_run = import_feedback_batch_and_run_learning(
            session,
            tenant_id=tenant_id,
            created_by=user.id,
            filename=filename,
            content=content,
            apply_region_adjustments=apply_region_adjustments,
            apply_success_adjustment=apply_success_adjustment,
        )
    except ValueError as exc:
        raise ParseError(str(exc))
    except Exception:
        raise ParseError("复盘学习表格解析失败，请检查文件格式和表头")

    out = ModelFeedbackBatchImportResult(
        filename=filename,
        total_rows=parsed.total_rows,
        imported_rows=len(created_rows),
        error_rows=parsed.error_rows,
        errors=parsed.errors[:100],
        detected_columns=parsed.detected_columns,
        unmapped_columns=parsed.unmapped_columns,
        learning_run=serialize_learning_run(learning_run) if learning_run else None,
    )
    audit_service.record(
        session,
        request,
        action="model_feedback.outcome_batch_import",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="model_learning_run" if learning_run else "disposal_outcome",
        resource_id=learning_run.id if learning_run else None,
        after={
            "filename": filename,
            "total_rows": parsed.total_rows,
            "imported_rows": len(created_rows),
            "error_rows": parsed.error_rows,
            "apply_region_adjustments": apply_region_adjustments,
            "apply_success_adjustment": apply_success_adjustment,
        },
    )
    return out


@router.get(
    "/summary",
    response_model=ModelFeedbackSummary,
    dependencies=[Depends(require_role("operator"))],
)
async def summary(
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return compute_feedback_summary(session, tenant_id=tenant_id)


@router.get(
    "/learning-runs",
    response_model=list[ModelLearningRunOut],
    dependencies=[Depends(require_role("operator"))],
)
async def list_learning_runs(
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    rows = model_feedback_repo.list_learning_runs(
        session,
        tenant_id=tenant_id,
        limit=limit,
    )
    return [serialize_learning_run(row) for row in rows]


@router.post(
    "/learning-runs",
    response_model=ModelLearningRunOut,
    dependencies=[Depends(require_role("manager"))],
)
async def create_learning_run(
    req: ModelLearningRunCreate,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    row = run_learning_cycle(
        session,
        tenant_id=tenant_id,
        created_by=user.id,
        apply_region_adjustments=req.apply_region_adjustments,
        apply_success_adjustment=req.apply_success_adjustment,
    )
    out = serialize_learning_run(row)
    audit_service.record(
        session,
        request,
        action="model_feedback.learning_run",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="model_learning_run",
        resource_id=row.id,
        after=out.model_dump(),
    )
    return out
