import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 车300 API
    che300_access_key: str = ""
    che300_access_secret: str = ""
    che300_api_base: str = "https://cloud-api.che300.com"

    # DeepSeek LLM
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"

    # 应用配置
    database_path: str = os.path.join(os.path.dirname(__file__), "data", "npl.db")
    upload_dir: str = os.path.join(os.path.dirname(__file__), "data", "uploads")
    default_city_code: str = "320100"
    default_city_name: str = "南京"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    class Config:
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")

settings = Settings()
