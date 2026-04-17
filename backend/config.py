import os
from pydantic_settings import BaseSettings

_THIS_DIR = os.path.dirname(__file__)


class Settings(BaseSettings):
    # ---------- Database ----------
    # PostgreSQL (生产目标, Task 3+)
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/auto_finance"
    # Legacy only: historical SQLite path retained for manual inspection.
    # Application runtime no longer uses this as a supported DB entrypoint.
    database_path: str = os.path.join(_THIS_DIR, "data", "npl.db")

    # ---------- Redis (Task 8+) ----------
    redis_url: str = "redis://localhost:6379/0"

    # ---------- Auth (Task 5+) ----------
    jwt_secret: str = "dev-only-change-me"
    jwt_refresh_secret: str = "dev-only-change-me-refresh"

    # ---------- CORS ----------
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ---------- File Storage ----------
    storage_backend: str = "local"  # "local" | "s3"
    upload_dir: str = os.path.join(_THIS_DIR, "data", "uploads")
    s3_endpoint: str = ""
    s3_bucket: str = "auto-finance"
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # ---------- 车300 API ----------
    che300_access_key: str = ""
    che300_access_secret: str = ""
    che300_api_base: str = "https://cloud-api.che300.com"
    default_city_code: str = "320100"
    default_city_name: str = "南京"

    che300_basic_unit_cost: float = 1.5
    che300_condition_pricing_unit_cost: float = 36.0
    # ---------- LLM ----------
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    llm_model: str = ""

    llm_turbo_unit_cost: float = 0.2
    llm_plus_unit_cost: float = 0.8
    llm_long_unit_cost: float = 1.5
    class Config:
        env_file = os.path.join(_THIS_DIR, "..", ".env")


settings = Settings()
