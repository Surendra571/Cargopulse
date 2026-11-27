import os
from typing import Any, List, Optional, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Application
    APP_NAME: str = "CargoPulse"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v: Any) -> bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "dev", "development")
        return bool(v)

    # Security
    SECRET_KEY: str = "cargopulse_dev_super_secret_key_change_in_production_minimum_32_characters_long"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    RESET_TOKEN_EXPIRE_MINUTES: int = 60
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    COOKIE_REFRESH_NAME: str = "cargopulse_refresh_token"
    COOKIE_CSRF_NAME: str = "cargopulse_csrf_token"

    # CORS
    ALLOWED_ORIGINS: Union[List[str], str] = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # Database (PostgreSQL)
    POSTGRES_SERVER: str = "127.0.0.1"
    POSTGRES_PORT: int = 5433
    POSTGRES_DB: str = "cargopulse"
    POSTGRES_USER: str = "cargopulse_user"
    POSTGRES_PASSWORD: str = ""
    DATABASE_URL: str = "postgresql+asyncpg://cargopulse_user@127.0.0.1:5433/cargopulse"
    DATABASE_SYNC_URL: str = "postgresql+psycopg2://cargopulse_user@127.0.0.1:5433/cargopulse"

    # Database Connection Pool Settings
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # Redis Cache & PubSub
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""
    REDIS_URL: str = "redis://127.0.0.1:6379/0"

    # Celery Background Processing
    CELERY_BROKER_URL: str = "redis://127.0.0.1:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://127.0.0.1:6379/2"
    CELERY_TASK_ALWAYS_EAGER: bool = False

    # Object Storage (S3-compatible)
    STORAGE_BACKEND: str = "local"  # 's3' or 'local'
    S3_ENDPOINT_URL: Optional[str] = None
    S3_REGION_NAME: str = "us-east-1"
    S3_BUCKET_NAME: str = "cargopulse-epod"
    S3_ACCESS_KEY_ID: Optional[str] = None
    S3_SECRET_ACCESS_KEY: Optional[str] = None
    LOCAL_STORAGE_DIR: str = "storage/uploads"
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_MIME_TYPES: List[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "application/pdf",
    ]

    # Logging & Error Monitoring
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    SENTRY_DSN: Optional[str] = None
    RATE_LIMIT_ENABLED: bool = True

    def validate_production_settings(self) -> None:
        """Fail fast if unsafe development defaults are used in production."""
        if self.ENVIRONMENT.lower() != "production":
            return

        errors: List[str] = []
        if (
            not self.SECRET_KEY
            or self.SECRET_KEY.startswith("cargopulse_dev_")
            or len(self.SECRET_KEY) < 32
        ):
            errors.append("SECRET_KEY must be a unique >=32-character secret in production.")
        if self.DEBUG:
            errors.append("DEBUG must be false in production.")
        if not self.COOKIE_SECURE:
            errors.append("COOKIE_SECURE must be true in production (HTTPS required).")
        if "*" in self.ALLOWED_ORIGINS:
            errors.append("ALLOWED_ORIGINS must not contain wildcard '*' in production.")
        if self.POSTGRES_PASSWORD in ("", "cargopulse_dev_password"):
            errors.append("POSTGRES_PASSWORD must not use empty or development default in production.")

        if errors:
            raise RuntimeError("Invalid production configuration: " + " | ".join(errors))


settings = Settings()
