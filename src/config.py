from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.constants import (
    DEFAULT_APP_NAME,
    DEFAULT_APP_VERSION,
)


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.

    Centralizes all tunable parameters including application metadata,
    database connectivity, hygiene scoring, SLA thresholds, and batch processing.
    """

    # -------------------
    # Application metadata
    # -------------------
    app_name: str = Field(
        default=DEFAULT_APP_NAME,
        validation_alias=AliasChoices("APP_NAME"),
    )
    app_version: str = Field(
        default=DEFAULT_APP_VERSION,
        validation_alias=AliasChoices("APP_VERSION"),
    )
    debug: bool = Field(
        default=False,
        validation_alias=AliasChoices("DEBUG"),
    )

    # -------------------
    # Database connection
    # -------------------
    db_host: str = Field(
        ...,
        validation_alias=AliasChoices("DB_HOST"),
    )
    db_port: int = Field(
        default=5432,
        validation_alias=AliasChoices("DB_PORT"),
    )
    db_name: str = Field(
        ...,
        validation_alias=AliasChoices("DB_NAME"),
    )
    db_user: str = Field(
        ...,
        validation_alias=AliasChoices("DB_USER"),
    )
    db_password: str = Field(
        ...,
        validation_alias=AliasChoices("DB_PASSWORD"),
    )

    # -------------------
    # Derived properties
    # -------------------
    @property
    def database_url(self) -> str:
        """Construct SQLAlchemy-compatible database URL."""
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # -------------------
    # Pydantic v2 config
    # -------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# Singleton instance
settings = Settings()
