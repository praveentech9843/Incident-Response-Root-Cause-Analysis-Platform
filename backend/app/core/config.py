from typing import List, Optional, Union
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import json


def normalize_database_url(url: Union[str, None]) -> str:
    """
    Normalizes PostgreSQL database URLs to ensure SQLAlchemy strictly selects
    the psycopg2 driver and prevents driver mismatch errors (e.g. Missing psycopg v3).

    Handles:
    - postgres:// -> postgresql:// (legacy/Heroku/Render cloud format)
    - postgresql+psycopg:// -> postgresql:// (prevents ModuleNotFoundError: No module named 'psycopg')
    - postgres+psycopg:// -> postgresql://
    - postgres+psycopg2:// -> postgresql+psycopg2://
    Preserves:
    - postgresql:// -> postgresql:// (defaults to psycopg2 in SQLAlchemy)
    - postgresql+psycopg2:// -> postgresql+psycopg2:// (explicit psycopg2)
    - sqlite:// -> sqlite://
    """
    if not url or not isinstance(url, str):
        return ""
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql://", 1)
    if url.startswith("postgres+psycopg://"):
        return url.replace("postgres+psycopg://", "postgresql://", 1)
    if url.startswith("postgres+psycopg2://"):
        return url.replace("postgres+psycopg2://", "postgresql+psycopg2://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Application
    APP_NAME: str = "AI-Powered Incident Response & RCA Platform"
    APP_ENV: str = "development"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Security
    SECRET_KEY: str = "development-secret-key-do-not-use-in-production-32bytes-min"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # API Prefix
    API_V1_PREFIX: str = "/api/v1"

    # API Documentation Settings
    ENABLE_DOCS: bool = True
    DOCS_URL: Optional[str] = "/docs"
    OPENAPI_URL: Optional[str] = "/openapi.json"
    REDOC_URL: Optional[str] = "/redoc"

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/incident_platform_dev"
    TEST_DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/incident_platform_test"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    # Ingestion Settings
    MAX_LOG_UPLOAD_SIZE_MB: int = 10

    # Phase 3: Incident Correlation Settings
    INCIDENT_CORRELATION_WINDOW_SECONDS: int = 30

    # Phase 5: RCA Settings
    RCA_PROVIDER: str = "none"  # "none", "mock", "openai", "gemini", "anthropic"
    RCA_MODEL: str = "none"
    RCA_API_KEY: str = ""
    RCA_BASE_URL: str = ""

    # Phase 6: Recommendation Settings
    RECOMMENDATION_PROVIDER: str = "none"  # "none", "mock", "openai", "gemini", "anthropic"
    RECOMMENDATION_MODEL: str = "none"
    RECOMMENDATION_API_KEY: str = ""
    RECOMMENDATION_BASE_URL: str = ""

    # Phase 8: Auth & RBAC
    AUTH_STRICT: bool = False
    JWT_ACCESS_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_DAYS: int = 7

    # Phase 8: External Integrations
    GITHUB_ENABLED: bool = False
    GITHUB_TOKEN: str = ""
    GITHUB_REPO: str = ""

    PROMETHEUS_ENABLED: bool = False
    PROMETHEUS_URL: str = ""

    KUBERNETES_ENABLED: bool = False
    KUBERNETES_NAMESPACE: str = "default"

    # Phase 8: Notifications & Alerting
    SLACK_ENABLED: bool = False
    SLACK_TOKEN: str = ""
    SLACK_DEFAULT_CHANNEL: str = "incidents"

    PAGERDUTY_ENABLED: bool = False
    PAGERDUTY_TOKEN: str = ""

    EMAIL_ENABLED: bool = False
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # CORS
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    @field_validator("DATABASE_URL", "TEST_DATABASE_URL", mode="before")
    @classmethod
    def assemble_database_url(cls, v: Union[str, None]) -> str:
        return normalize_database_url(v)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return ["http://localhost:5173", "http://127.0.0.1:5173"]

    @model_validator(mode="after")
    def enforce_test_database_isolation(self) -> "Settings":
        if self.APP_ENV == "test" and "incident_platform_dev" in (self.DATABASE_URL or ""):
            self.DATABASE_URL = self.TEST_DATABASE_URL
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
