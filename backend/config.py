import os
from pydantic_settings import BaseSettings, SettingsConfigDict

_THIS_DIR = os.path.dirname(__file__)
DEFAULT_JWT_SECRET = "dev-only-change-me"
DEFAULT_JWT_REFRESH_SECRET = "dev-only-change-me-refresh"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=os.path.join(_THIS_DIR, "..", ".env"))

    app_env: str = "development"

    # ---------- Database ----------
    # PostgreSQL (生产目标, Task 3+)
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/auto_finance"
    # Legacy only: historical SQLite path retained for manual inspection.
    # Application runtime no longer uses this as a supported DB entrypoint.
    database_path: str = os.path.join(_THIS_DIR, "data", "npl.db")

    # ---------- Redis (Task 8+) ----------
    redis_url: str = "redis://localhost:6379/0"

    # ---------- Auth (Task 5+) ----------
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_refresh_secret: str = DEFAULT_JWT_REFRESH_SECRET

    # ---------- CORS ----------
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    cors_allow_methods: str = "GET,POST,PUT,DELETE,OPTIONS"

    # ---------- Rate Limiting ----------
    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = 60
    rate_limit_login_max_requests: int = 10
    rate_limit_register_max_requests: int = 5
    rate_limit_access_request_max_requests: int = 3
    rate_limit_write_max_requests: int = 30

    # ---------- 注册开关（内测期建议关闭公开注册，改走申请制）----------
    allow_public_registration: bool = True
    # 当前生效的服务条款/隐私须知版本号 —— 每次文本变更时递增
    terms_version: str = "2026.04.21"
    default_registration_tenant_code: str = "default"
    default_registration_tenant_name: str = "默认租户"

    # ---------- File Storage ----------
    storage_backend: str = "local"  # "local" | "s3"
    upload_dir: str = os.path.join(_THIS_DIR, "data", "uploads")
    # 单次上传 Excel 的最大字节数（默认 10 MiB）
    upload_excel_max_bytes: int = 10 * 1024 * 1024
    s3_endpoint: str = ""
    s3_public_base_url: str = ""
    s3_bucket: str = "auto-finance"
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # ---------- 车300 API ----------
    che300_access_key: str = ""
    che300_access_secret: str = ""
    che300_api_base: str = "https://cloud-api.che300.com"
    # 估值后端模式:
    #   "auto" (默认)  - 有合法 key 走真 API,没 key / 占位符 key 自动 fallback mock
    #   "real"        - 强制走真车300 API,即使 key 为空也尝试(用于生产排错)
    #   "mock"        - 强制走本地 mock 估值,完全不联网(用于演示/测试)
    # 历史问题:之前判断仅看 "key 是否非空字符串",`disabled_for_demo` 这种占位符
    # 会被误判为"有 key" 然后调真 API 失败 → 估值 0%。本字段是修复。
    che300_mode: str = "auto"
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


settings = Settings()
