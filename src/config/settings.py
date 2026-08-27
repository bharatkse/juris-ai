from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, model_validator

from config.base import AppSettings, BaseAppSettings
from config.database import DatabaseSettings
from config.llm import LLMSettings
from config.logging import LoggingSettings
from config.security import SecuritySettings
from core.enums import EnvironmentEnum


class Settings(BaseAppSettings):
    """Aggregated application settings composition."""

    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)

    # --------------------------------------------------------------------------
    # Backward Compatibility Proxies
    # --------------------------------------------------------------------------
    @property
    def async_database_url(self) -> str:
        return self.database.get_async_database_url(self.app.ENVIRONMENT)

    @property
    def database_url(self) -> str:
        return self.database.get_sync_database_url(self.app.ENVIRONMENT)

    @property
    def langgraph_database_url(self) -> str:
        return self.database.get_langgraph_database_url()

    # --------------------------------------------------------------------------
    # Global Cross-Sectional Validator
    # --------------------------------------------------------------------------
    @model_validator(mode="after")
    def validate_environment_consistency(self) -> Settings:
        if self.app.is_testing:
            return self

        env = self.app.ENVIRONMENT

        if env is EnvironmentEnum.DEVELOPMENT:
            required = {
                "SECRET_KEY": self.security.SECRET_KEY,
                "DB_HOST": self.database.DB_HOST,
                "DB_NAME": self.database.DB_NAME,
                "DB_USER": self.database.DB_USER,
                "DB_PASSWORD": self.database.DB_PASSWORD,
                "GROQ_API_KEY": self.llm.GROQ_API_KEY,
            }
            self._check_missing(required)

        elif env is EnvironmentEnum.STAGING:
            required = {
                "SECRET_KEY": self.security.SECRET_KEY,
                "DB_HOST": self.database.DB_HOST,
                "DB_NAME": self.database.DB_NAME,
                "DB_USER": self.database.DB_USER,
                "DB_PASSWORD": self.database.DB_PASSWORD,
            }
            self._check_missing(required)

        elif env is EnvironmentEnum.PRODUCTION:
            self._check_missing({"SECRET_KEY": self.security.SECRET_KEY})

        if self.app.OTEL_TRACING:
            self._check_missing(
                {
                    "OTEL_EXPORTER_OTLP_ENDPOINT": self.app.OTEL_EXPORTER_OTLP_ENDPOINT,
                    "OTEL_APP_VERSION": self.app.OTEL_APP_VERSION,
                    "OTEL_EXPORTER_OTLP_PROTOCOL": self.app.OTEL_EXPORTER_OTLP_PROTOCOL,
                }
            )

        return self

    @staticmethod
    def _check_missing(fields: dict[str, Any]) -> None:
        missing = [k for k, v in fields.items() if v is None or v == ""]
        if missing:
            raise ValueError(f"Missing required settings: {', '.join(missing)}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
