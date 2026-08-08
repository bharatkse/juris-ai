"""
Central configuration loaded from environment variables.
All other modules import `settings` from here — never read os.environ directly.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.constants import DEFAULT_APP_NAME, DEFAULT_APP_VERSION, TEST_DB_URL
from src.core.enums import CacheBackend, Environment, GroqModel


class Settings(BaseSettings):
    """
    Central application configuration loaded from environment variables.

    This class is the single source of truth for all runtime configuration.
    Never access environment variables directly outside this module.
    """

    # --------------------------------------------------------------------------
    # Application
    # --------------------------------------------------------------------------

    APP_NAME: str = DEFAULT_APP_NAME
    APP_VERSION: str = DEFAULT_APP_VERSION

    ENVIRONMENT: Environment = Environment.DEVELOPMENT

    DEBUG: bool = False

    SECRET_KEY: str | None = Field(
        default=None,
        description="Application secret key used for signing JWTs and sessions.",
    )

    # --------------------------------------------------------------------------
    # Server
    # --------------------------------------------------------------------------

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    WORKERS: int = 1
    RELOAD: bool = False

    # --------------------------------------------------------------------------
    # Database
    # --------------------------------------------------------------------------
    DB_HOST: str | None = None
    DB_PORT: int = 5432

    DB_NAME: str | None = None
    DB_USER: str | None = None
    DB_PASSWORD: str | None = None

    DATABASE_ECHO: bool = False

    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 1800

    TEST_DATABASE_URL: str = TEST_DB_URL

    # --------------------------------------------------------------------------
    # Cache / Redis
    # --------------------------------------------------------------------------

    CACHE_BACKEND: CacheBackend = CacheBackend.REDIS

    CACHE_TTL: int = 3600
    CACHE_MAX_SIZE: int = 1000

    REDIS_URL: str = "redis://localhost:6379/0"

    # --------------------------------------------------------------------------
    # Logging
    # --------------------------------------------------------------------------

    LOG_LEVEL: Literal[
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ] = "INFO"

    LOG_FORMAT: Literal["json", "text"] = "json"

    LOG_FILE: str = "./logs/app.log"
    DATA_DIRECTORY: str = "./data"
    LOG_DIRECTORY: str = "./logs"

    LOG_MAX_MB: int = 100
    LOG_BACKUP_COUNT: int = 5

    # --------------------------------------------------------------------------
    # API
    # --------------------------------------------------------------------------

    API_PREFIX: str = "/api/v1"

    ENABLE_DOCS: bool = True

    CORS_ORIGINS: list[str] = ["*"]

    # --------------------------------------------------------------------------
    # External Services
    # --------------------------------------------------------------------------
    GROQ_API_KEY: SecretStr | None = None
    GROQ_MODEL: GroqModel = GroqModel.LLAMA_3_3_70B

    # --------------------------------------------------------------------------
    # Pydantic Configuration
    # --------------------------------------------------------------------------

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        validate_assignment=True,
    )

    # --------------------------------------------------------------------------
    # Validators
    # --------------------------------------------------------------------------
    @staticmethod
    def _validate_positive(value: int, field: str) -> int:
        if value <= 0:
            raise ValueError(f"{field} must be greater than zero.")
        return value

    @field_validator("PORT", "DB_PORT")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if not (1 <= value <= 65535):
            raise ValueError("Port must be between 1 and 65535.")
        return value

    @field_validator(
        "DATABASE_POOL_SIZE",
        "DATABASE_MAX_OVERFLOW",
        "DATABASE_POOL_TIMEOUT",
        "DATABASE_POOL_RECYCLE",
    )
    @classmethod
    def validate_positive_numbers(cls, value: int) -> int:
        return cls._validate_positive(value, "Database configuration")

    @field_validator("CACHE_TTL")
    @classmethod
    def validate_cache_ttl(cls, value):
        return cls._validate_positive(value, "CACHE_TTL")

    # --------------------------------------------------------------------------
    # Convenience Properties
    # --------------------------------------------------------------------------

    @property
    def database_url(self) -> str:
        if self.is_testing:
            return self.TEST_DATABASE_URL

        if self.is_development:
            return (
                f"postgresql+asyncpg://"
                f"{self.DB_USER}:{self.DB_PASSWORD}"
                f"@{self.DB_HOST}:{self.DB_PORT}"
                f"/{self.DB_NAME}"
            )
        else:
            raise NotImplementedError

    @property
    def alembic_database_url(self) -> str:
        return (
            f"postgresql+psycopg://"
            f"{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def redis_enabled(self) -> bool:
        return self.CACHE_BACKEND is CacheBackend.REDIS

    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT is Environment.TESTING

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT is Environment.DEVELOPMENT

    # --------------------------------------------------------------------------
    # Validation Helpers
    # --------------------------------------------------------------------------
    @model_validator(mode="after")
    def validate_configuration(self) -> Settings:
        if self.is_testing:
            return self

        required_fields = {
            Environment.DEVELOPMENT: {
                "SECRET_KEY": self.SECRET_KEY,
                "DB_HOST": self.DB_HOST,
                "DB_NAME": self.DB_NAME,
                "DB_USER": self.DB_USER,
                "DB_PASSWORD": self.DB_PASSWORD,
                "GROQ_API_KEY": self.GROQ_API_KEY,
            },
            Environment.STAGING: {
                "SECRET_KEY": self.SECRET_KEY,
                "DB_HOST": self.DB_HOST,
                "DB_NAME": self.DB_NAME,
                "DB_USER": self.DB_USER,
                "DB_PASSWORD": self.DB_PASSWORD,
            },
            Environment.PRODUCTION: {
                "SECRET_KEY": self.SECRET_KEY,
            },
        }

        self._validate_required_fields(required_fields[self.ENVIRONMENT])

        return self

    def _validate_required_fields(self, required_fields: dict[str, Any]) -> None:
        missing = [key for key, value in required_fields.items() if value is None or value == ""]

        if missing:
            raise ValueError(f"Missing required settings: {', '.join(missing)}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()


# Module-level singleton used by all other modules
settings: Settings = get_settings()
