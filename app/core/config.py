from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "StockFlow OMS"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    debug: bool = False

    database_url: str = Field(
        default="sqlite:///./stockflow.db",
        description="SQLAlchemy database URL. PostgreSQL example: postgresql+psycopg2://user:pass@db:5432/stockflow",
    )
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    default_admin_email: str = "admin@example.com"
    default_admin_password: str = "admin123"
    default_admin_name: str = "System Admin"

    low_stock_threshold: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
