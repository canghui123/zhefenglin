"""Legal document generation API."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import get_current_user, require_role
from errors import InvalidLegalDocumentRequest, WorkOrderNotFound
from models.legal_document import LegalDocumentGenerateRequest, LegalDocumentResult
from repositories import work_order_repo
from services import audit_service  # noqa: F401
from services.legal_document_generator import generate_legal_document
from services.tenant_context import get_current_tenant_id
from services.work_order_service import serialize_work_order, update_work_order_status


router = APIRouter(
    prefix="/api/legal-documents",
    tags=["法务材料"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/generate",
    response_model=LegalDocumentResult,
    dependencies=[Depends(require_role("operator"))],
)
async def generate_document(
    req: LegalDocumentGenerateRequest,
    request: Request,
    session: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    tenant_id: int = Depends(get_current_tenant_id),
):
    before = None
    if req.work_order_id is not None:
        work_order = work_order_repo.get_work_order_by_id(
            session,
            req.work_order_id,
            tenant_id=tenant_id,
        )
        if work_order is None:
            raise WorkOrderNotFound()
        if work_order.order_type != "legal_document":
            raise InvalidLegalDocumentRequest("只能关联法务材料工单")
        before = serialize_work_order(work_order).model_dump()

    result = generate_legal_document(req)

    if req.work_order_id is not None:
        updated = update_work_order_status(
            session,
            tenant_id=tenant_id,
            work_order_id=req.work_order_id,
            status="completed",
            result={
                "document_type": result.document_type,
                "title": result.title,
                "generated_at": result.generated_at.isoformat(),
                "html": result.html,
            },
        )
        after = serialize_work_order(updated).model_dump()
    else:
        after = {
            "document_type": result.document_type,
            "title": result.title,
        }

    audit_service.record(
        session,
        request,
        action="legal_document.generate",
        tenant_id=tenant_id,
        user_id=user.id,
        resource_type="legal_document",
        resource_id=req.work_order_id,
        before=before,
        after=after,
    )
    return result
