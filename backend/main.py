"""FastAPI主入口"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from database import init_db
from errors import BusinessError
from logging_config import setup_logging
from schemas.error import ErrorEnvelope  # noqa: F401 — used in OpenAPI
from api.auth import router as auth_router
from api.car_valuation import router as valuation_router
from api.asset_package import router as asset_router
from api.inventory_sandbox import router as sandbox_router
from api.portfolio import router as portfolio_router
from api.jobs import router as jobs_router
from api.metrics import router as metrics_router
from api.admin import router as admin_router
from api.external_data import router as external_data_router
from api.work_orders import router as work_orders_router
from api.legal_documents import router as legal_documents_router
from middleware.request_context import RequestContextMiddleware
from middleware.metrics import MetricsMiddleware


setup_logging(json=os.environ.get("LOG_FORMAT") != "console")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema for PostgreSQL is owned by Alembic (`alembic upgrade head`).
    # Only the legacy SQLite path bootstraps tables in-process.
    if settings.database_url.startswith("sqlite") or os.environ.get("DATABASE_PATH"):
        init_db()
    yield


app = FastAPI(
    title="汽车金融不良资产AI平台",
    description="AI智能定价与库存决策引擎",
    version="0.1.0",
    lifespan=lifespan,
    responses={
        401: {"model": ErrorEnvelope, "description": "未认证"},
        403: {"model": ErrorEnvelope, "description": "权限不足"},
        404: {"model": ErrorEnvelope, "description": "资源不存在"},
        422: {"model": ErrorEnvelope, "description": "参数校验失败"},
    },
)

def _get_request_id(request: Request) -> str:
    return getattr(getattr(request, "state", None), "request_id", "")


@app.exception_handler(BusinessError)
async def _business_error_handler(request: Request, exc: BusinessError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": _get_request_id(request),
                "details": exc.details,
            }
        },
    )


@app.exception_handler(HTTPException)
async def _http_exception_handler(request: Request, exc: HTTPException):
    code_map = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code_map.get(exc.status_code, f"HTTP_{exc.status_code}"),
                "message": exc.detail or "",
                "request_id": _get_request_id(request),
                "details": {},
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "请求参数校验失败",
                "request_id": _get_request_id(request),
                "details": {"errors": exc.errors()},
            }
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Stamps request_id / client_ip / user_agent on `request.state` so audit
# rows recorded later in the request can pull them out without re-parsing
# the headers themselves.
app.add_middleware(RequestContextMiddleware)
app.add_middleware(MetricsMiddleware)

app.include_router(auth_router)
app.include_router(valuation_router)
app.include_router(asset_router)
app.include_router(sandbox_router)
app.include_router(portfolio_router)
app.include_router(jobs_router)
app.include_router(metrics_router)
app.include_router(admin_router)
app.include_router(external_data_router)
app.include_router(work_orders_router)
app.include_router(legal_documents_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "汽车金融不良资产AI平台"}
