import os
from pydantic_settings import BaseSettings

_THIS_DIR = os.path.dirname(__file__)


class Settings(BaseSettings):
    # ---------- Database ----------
    # PostgreSQL (生产目标, Task 3+)
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/auto_finance"
    # SQLite (本地开发兼容, 将逐步淘汰)
    database_path: str = os.path.join(_THIS_DIR, "data", "npl.db")

    # ---------- Redis (Task 8+) ----------
    redis_url: str = "redis://localhost:6379/0"

    # ---------- Auth (Task 5+) ----------
    jwt_secret: str = "dev-only-change-me"
    jwt_refresh_secret: str = "dev-only-change-me-refresh"
    default_registration_tenant_code: str = "default"
    default_registration_tenant_name: str = "默认租户"

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

    # ---------- LLM ----------
    llm_provider: str = "qwen"
    llm_api_key: str = ""
    llm_base_url: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"
    dashscope_api_key: str = ""
    dashscope_base_url: str = ""
    llm_model: str = "qwen-plus"

    class Config:
        env_file = os.path.join(_THIS_DIR, "..", ".env")


settings = Settings()
