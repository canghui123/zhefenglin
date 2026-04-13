"""Job status / listing endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.models.user import User
from db.session import get_db_session
from dependencies.auth import get_current_user
from services.job_dispatcher import get_job, list_jobs
from services.tenant_context import get_current_tenant_id

router = APIRouter(
    prefix="/api/jobs",
    tags=["任务"],
    dependencies=[Depends(get_current_user)],
)


def _serialize(job):
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "payload_json": job.payload_json,
        "result_json": job.result_json,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


@router.get("/list")
async def job_list(
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    return [_serialize(j) for j in list_jobs(session, tenant_id=tenant_id)]


@router.get("/{job_id}")
async def job_status(
    job_id: int,
    session: Session = Depends(get_db_session),
    tenant_id: int = Depends(get_current_tenant_id),
):
    job = get_job(session, job_id)
    if job is None or job.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _serialize(job)
