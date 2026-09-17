from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.constants import DEFAULT_APP_NAME, DEFAULT_APP_VERSION
from core.enums import EnvironmentEnum


class BaseAppSettings(BaseSettings):
    """Base settings class with shared environment configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        validate_assignment=True,
    )


class AppSettings(BaseAppSettings):
    """Core server and application metadata."""

    APP_NAME: str = DEFAULT_APP_NAME
    APP_VERSION: str = DEFAULT_APP_VERSION
    ENVIRONMENT: EnvironmentEnum = EnvironmentEnum.DEVELOPMENT
    DEBUG: bool = False

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1
    RELOAD: bool = False

    API_PREFIX: str = "/api/v1"
    ENABLE_DOCS: bool = True
    CORS_ORIGINS: list[str] = ["*"]

    # OpenTelemetry
    OTEL_TRACING: bool = False
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4318/v1/traces"
    OTEL_APP_VERSION: str = "0.1.0"
    OTEL_EXPORTER_OTLP_PROTOCOL: str | None = None

    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT is EnvironmentEnum.TESTING

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT is EnvironmentEnum.DEVELOPMENT

    @field_validator("PORT")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if not (1 <= value <= 65535):
            raise ValueError("PORT must be between 1 and 65535.")
        return value
