from __future__ import annotations

from pydantic import field_validator

from config.base import BaseAppSettings
from core.constants import TEST_DB_URL
from core.enums import EnvironmentEnum


class DatabaseSettings(BaseAppSettings):
    """PostgreSQL connection and connection pool configuration."""

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

    @field_validator("DB_PORT")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if not (1 <= value <= 65535):
            raise ValueError("DB_PORT must be between 1 and 65535.")
        return value

    @field_validator(
        "DATABASE_POOL_SIZE",
        "DATABASE_MAX_OVERFLOW",
        "DATABASE_POOL_TIMEOUT",
        "DATABASE_POOL_RECYCLE",
    )
    @classmethod
    def validate_positive_numbers(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Database pool values must be greater than zero.")
        return value

    def get_async_database_url(self, environment: EnvironmentEnum) -> str:
        if environment is EnvironmentEnum.TESTING:
            return self.TEST_DATABASE_URL
        if environment is EnvironmentEnum.DEVELOPMENT:
            return (
                f"postgresql+asyncpg://"
                f"{self.DB_USER}:{self.DB_PASSWORD}"
                f"@{self.DB_HOST}:{self.DB_PORT}"
                f"/{self.DB_NAME}"
            )
        raise NotImplementedError("Async URL not implemented for this environment.")

    def get_sync_database_url(self, environment: EnvironmentEnum) -> str:
        if environment is EnvironmentEnum.TESTING:
            return self.TEST_DATABASE_URL
        return (
            f"postgresql+psycopg://"
            f"{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    def get_langgraph_database_url(self) -> str:
        return (
            f"postgresql://"
            f"{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )
