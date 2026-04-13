"""FastAPI主入口"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db
from logging_config import setup_logging
from api.auth import router as auth_router
from api.car_valuation import router as valuation_router
from api.asset_package import router as asset_router
from api.inventory_sandbox import router as sandbox_router
from api.portfolio import router as portfolio_router
from api.jobs import router as jobs_router
from api.metrics import router as metrics_router
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


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "汽车金融不良资产AI平台"}
