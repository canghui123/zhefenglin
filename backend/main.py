"""FastAPI主入口"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
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
from api.admin_settings import router as admin_settings_router
from api.admin_cost_center import router as admin_cost_center_router
from api.admin_feature_flags import router as admin_feature_flags_router
from api.admin_model_routing import router as admin_model_routing_router
from api.admin_valuation_rules import router as admin_valuation_rules_router
from api.admin_approval_requests import router as admin_approval_requests_router
from middleware.request_context import RequestContextMiddleware
from middleware.metrics import MetricsMiddleware


setup_logging(json=os.environ.get("LOG_FORMAT") != "console")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runtime schema management is externalized to Alembic.
    # The app no longer bootstraps legacy SQLite tables at startup.
    yield


app = FastAPI(
    title="汽车金融资产处置经营决策系统",
    description="汽车金融资产处置经营决策系统",
    version="0.1.0",
    lifespan=lifespan,
    responses={
        401: {"model": ErrorEnvelope, "description": "未认证"},
        403: {"model": ErrorEnvelope, "description": "权限不足"},
        404: {"model": ErrorEnvelope, "description": "资源不存在"},
        422: {"model": ErrorEnvelope, "description": "参数校验失败"},
    },
)


def _json_safe(value):
    if isinstance(value, BaseException):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_json_safe(item) for item in value)
    return value


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
                "details": {"errors": _json_safe(exc.errors())},
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
app.include_router(admin_settings_router)
app.include_router(admin_cost_center_router)
app.include_router(admin_feature_flags_router)
app.include_router(admin_model_routing_router)
app.include_router(admin_valuation_rules_router)
app.include_router(admin_approval_requests_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "汽车金融资产处置经营决策系统"}
