"""Job dispatcher — creates job_runs rows and executes them.

For the MVP the work is executed **inline** (synchronously in the same
request) so we don't need Redis/Celery. The 202 contract is already
established though, so a real queue can be plugged in later by replacing
``run_inline`` with ``enqueue``.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from db.models.job_run import JobRun
from services.metrics import JOBS_TOTAL


logger = logging.getLogger(__name__)


def _safe_error_message(exc: BaseException, *, limit: int = 200) -> str:
    """Return a short, user-facing error message without stack traces or paths.

    完整 traceback 由 logger.exception 记录到服务端日志；面向租户的
    ``job_runs.error_message`` 只保留异常类名 + 首行 str，且去掉路径。"""
    name = type(exc).__name__
    raw = (str(exc) or "").strip().splitlines()
    first_line = raw[0] if raw else ""
    # 去掉可能的绝对路径/长字符串
    if len(first_line) > limit:
        first_line = first_line[:limit] + "..."
    return f"{name}: {first_line}" if first_line else name


# ---------- repo helpers (kept inline, tiny) ----------

def _create(
    session: Session,
    *,
    tenant_id: int,
    requested_by: Optional[int],
    job_type: str,
    payload: Optional[dict] = None,
) -> JobRun:
    row = JobRun(
        tenant_id=tenant_id,
        requested_by=requested_by,
        job_type=job_type,
        status="queued",
        payload_json=json.dumps(payload, ensure_ascii=False) if payload else None,
    )
    session.add(row)
    session.flush()
    return row


def _mark_running(session: Session, job: JobRun) -> None:
    job.status = "running"
    job.started_at = datetime.utcnow()
    session.flush()


def _mark_succeeded(
    session: Session, job: JobRun, result: Optional[Any] = None
) -> None:
    job.status = "succeeded"
    job.finished_at = datetime.utcnow()
    if result is not None:
        job.result_json = json.dumps(result, ensure_ascii=False, default=str)
    session.flush()


def _mark_failed(
    session: Session, job: JobRun, *, code: str, message: str
) -> None:
    job.status = "failed"
    job.finished_at = datetime.utcnow()
    job.error_code = code
    job.error_message = message
    session.flush()


def get_job(session: Session, job_id: int) -> Optional[JobRun]:
    return session.get(JobRun, job_id)


def list_jobs(
    session: Session, *, tenant_id: int, limit: int = 50
) -> list:
    from sqlalchemy import select
    stmt = (
        select(JobRun)
        .where(JobRun.tenant_id == tenant_id)
        .order_by(JobRun.created_at.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


# ---------- public API ----------

def dispatch_inline(
    session: Session,
    *,
    tenant_id: int,
    requested_by: Optional[int],
    job_type: str,
    payload: Optional[dict] = None,
    fn: Callable[[], Any],
) -> JobRun:
    """Create a job record, run *fn* synchronously, and update the row.

    Returns the job row (status will be ``succeeded`` or ``failed``).
    """
    job = _create(
        session,
        tenant_id=tenant_id,
        requested_by=requested_by,
        job_type=job_type,
        payload=payload,
    )
    _mark_running(session, job)
    try:
        result = fn()
        _mark_succeeded(session, job, result=result)
        JOBS_TOTAL.labels(job_type=job_type, status="succeeded").inc()
    except Exception as exc:
        logger.exception(
            "job_dispatch failed",
            extra={"job_id": job.id, "tenant_id": tenant_id, "job_type": job_type},
        )
        _mark_failed(
            session,
            job,
            code=type(exc).__name__,
            message=_safe_error_message(exc),
        )
        JOBS_TOTAL.labels(job_type=job_type, status="failed").inc()
    return job


async def dispatch_inline_async(
    session: Session,
    *,
    tenant_id: int,
    requested_by: Optional[int],
    job_type: str,
    payload: Optional[dict] = None,
    fn: Callable[[], Any],
) -> JobRun:
    """Like ``dispatch_inline`` but *fn* may be a coroutine function.

    Awaits *fn()* if it returns a coroutine, otherwise calls it normally.
    """
    import asyncio

    job = _create(
        session,
        tenant_id=tenant_id,
        requested_by=requested_by,
        job_type=job_type,
        payload=payload,
    )
    _mark_running(session, job)
    try:
        result = fn()
        if asyncio.iscoroutine(result):
            result = await result
        _mark_succeeded(session, job, result=result)
        JOBS_TOTAL.labels(job_type=job_type, status="succeeded").inc()
    except Exception as exc:
        logger.exception(
            "job_dispatch failed",
            extra={"job_id": job.id, "tenant_id": tenant_id, "job_type": job_type},
        )
        _mark_failed(
            session,
            job,
            code=type(exc).__name__,
            message=_safe_error_message(exc),
        )
        JOBS_TOTAL.labels(job_type=job_type, status="failed").inc()
    return job
