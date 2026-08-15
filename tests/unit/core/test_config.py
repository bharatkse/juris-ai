"""
Unit tests for application settings.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from src.core.config import Settings, get_settings
from src.core.enums import CacheBackendEnum, EnvironmentEnum


def test_settings_allows_testing_without_required_fields() -> None:
    """
    It should allow creating settings in the testing environment without
    requiring external configuration.
    """

    settings = Settings(
        ENVIRONMENT=EnvironmentEnum.TESTING,
        LANGSMITH_TRACING=False,
        LANGSMITH_TRACING_V2=False,
    )

    assert settings.is_testing is True


def test_settings_accepts_valid_port() -> None:
    """
    It should accept a valid port number.
    """

    settings = Settings(
        ENVIRONMENT=EnvironmentEnum.TESTING,
        PORT=8080,
        LANGSMITH_TRACING=False,
        LANGSMITH_TRACING_V2=False,
    )

    assert settings.PORT == 8080


@pytest.mark.parametrize(
    "port",
    [
        0,
        -1,
        65536,
    ],
)
def test_settings_rejects_invalid_port(
    port: int,
) -> None:
    """
    It should reject invalid port numbers.
    """

    with pytest.raises(
        ValidationError,
    ):
        Settings(
            ENVIRONMENT=EnvironmentEnum.TESTING,
            PORT=port,
            LANGSMITH_TRACING=False,
            LANGSMITH_TRACING_V2=False,
        )


@pytest.mark.parametrize(
    "field",
    [
        "DATABASE_POOL_SIZE",
        "DATABASE_MAX_OVERFLOW",
        "DATABASE_POOL_TIMEOUT",
        "DATABASE_POOL_RECYCLE",
    ],
)
def test_settings_rejects_invalid_database_configuration(
    field: str,
) -> None:
    """
    It should reject non-positive database configuration values.
    """

    with pytest.raises(
        ValidationError,
    ):
        Settings(
            ENVIRONMENT=EnvironmentEnum.TESTING,
            LANGSMITH_TRACING=False,
            LANGSMITH_TRACING_V2=False,
            **{
                field: 0,
            },
        )


def test_settings_rejects_invalid_cache_ttl() -> None:
    """
    It should reject a non-positive cache TTL.
    """

    with pytest.raises(
        ValidationError,
    ):
        Settings(
            ENVIRONMENT=EnvironmentEnum.TESTING,
            CACHE_TTL=0,
            LANGSMITH_TRACING=False,
            LANGSMITH_TRACING_V2=False,
        )


def test_database_url_returns_test_database_url() -> None:
    """
    It should return the test database URL in the testing environment.
    """

    settings = Settings(
        ENVIRONMENT=EnvironmentEnum.TESTING,
        LANGSMITH_TRACING=False,
        LANGSMITH_TRACING_V2=False,
    )

    assert settings.database_url == settings.TEST_DATABASE_URL


def test_database_url_returns_postgres_url() -> None:
    """
    It should build the PostgreSQL connection URL.
    """

    settings = Settings(
        ENVIRONMENT=EnvironmentEnum.DEVELOPMENT,
        SECRET_KEY="secret",
        DB_HOST="localhost",
        DB_PORT=5432,
        DB_NAME="legal_ai",
        DB_USER="postgres",
        DB_PASSWORD="password",
        GROQ_API_KEY=SecretStr(
            "api-key",
        ),
        LANGSMITH_TRACING=False,
        LANGSMITH_TRACING_V2=False,
    )

    assert settings.database_url == (
        "postgresql+asyncpg://" "postgres:password" "@localhost:5432" "/legal_ai"
    )


def test_database_url_raises_for_production() -> None:
    """
    It should raise when requesting the database URL in production.
    """

    settings = Settings(
        ENVIRONMENT=EnvironmentEnum.PRODUCTION,
        SECRET_KEY="secret",
        LANGSMITH_TRACING=False,
        LANGSMITH_TRACING_V2=False,
    )

    with pytest.raises(
        NotImplementedError,
    ):
        _ = settings.database_url


def test_alembic_database_url() -> None:
    """
    It should build the Alembic database URL.
    """

    settings = Settings(
        ENVIRONMENT=EnvironmentEnum.TESTING,
        DB_HOST="localhost",
        DB_PORT=5432,
        DB_NAME="legal_ai",
        DB_USER="postgres",
        DB_PASSWORD="password",
        LANGSMITH_TRACING=False,
        LANGSMITH_TRACING_V2=False,
    )

    assert settings.alembic_database_url == (
        "postgresql+psycopg://" "postgres:password" "@localhost:5432/legal_ai"
    )


def test_is_testing() -> None:
    """
    It should identify the testing environment.
    """

    settings = Settings(
        ENVIRONMENT=EnvironmentEnum.TESTING,
        LANGSMITH_TRACING=False,
        LANGSMITH_TRACING_V2=False,
    )

    assert settings.is_testing is True
    assert settings.is_development is False


def test_is_development() -> None:
    """
    It should identify the development environment.
    """

    settings = Settings(
        ENVIRONMENT=EnvironmentEnum.DEVELOPMENT,
        SECRET_KEY="secret",
        DB_HOST="localhost",
        DB_NAME="legal_ai",
        DB_USER="postgres",
        DB_PASSWORD="password",
        GROQ_API_KEY=SecretStr(
            "api-key",
        ),
        LANGSMITH_TRACING=False,
        LANGSMITH_TRACING_V2=False,
    )

    assert settings.is_development is True
    assert settings.is_testing is False


def test_redis_enabled_when_using_redis() -> None:
    """
    It should report Redis as enabled.
    """

    settings = Settings(
        ENVIRONMENT=EnvironmentEnum.TESTING,
        CACHE_BACKEND=CacheBackendEnum.REDIS,
        LANGSMITH_TRACING=False,
        LANGSMITH_TRACING_V2=False,
    )

    assert settings.redis_enabled is True


def test_redis_disabled_when_using_memory_cache() -> None:
    """
    It should report Redis as disabled.
    """

    settings = Settings(
        ENVIRONMENT=EnvironmentEnum.TESTING,
        CACHE_BACKEND=CacheBackendEnum.MEMORY,
        LANGSMITH_TRACING=False,
        LANGSMITH_TRACING_V2=False,
    )

    assert settings.redis_enabled is False


def test_validate_configuration_requires_secret_key(clean_environment) -> None:
    """
    It should require a secret key in the development environment.
    """

    with pytest.raises(
        ValidationError,
        match="SECRET_KEY",
    ):
        Settings(
            ENVIRONMENT=EnvironmentEnum.DEVELOPMENT,
            _env_file=None,
            LANGSMITH_TRACING=False,
            LANGSMITH_TRACING_V2=False,
        )


def test_validate_configuration_requires_database_configuration() -> None:
    """
    It should require database configuration in the development environment.
    """

    with pytest.raises(
        ValidationError,
        match="DB_HOST",
    ):
        Settings(
            ENVIRONMENT=EnvironmentEnum.DEVELOPMENT,
            SECRET_KEY="secret",
            _env_file=None,
            LANGSMITH_TRACING=False,
            LANGSMITH_TRACING_V2=False,
        )


def test_validate_configuration_requires_groq_api_key(monkeypatch) -> None:
    """
    It should require a Groq API key in the development environment.
    """
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(
        ValidationError,
        match="GROQ_API_KEY",
    ):
        Settings(
            ENVIRONMENT=EnvironmentEnum.DEVELOPMENT,
            SECRET_KEY="secret",
            DB_HOST="localhost",
            DB_NAME="legal_ai",
            DB_USER="postgres",
            DB_PASSWORD="password",
            _env_file=None,
            LANGSMITH_TRACING=False,
            LANGSMITH_TRACING_V2=False,
        )


def test_validate_required_fields_raises() -> None:
    """
    It should raise when required fields are missing.
    """

    settings = Settings(
        ENVIRONMENT=EnvironmentEnum.TESTING,
        LANGSMITH_TRACING=False,
        LANGSMITH_TRACING_V2=False,
    )

    with pytest.raises(
        ValueError,
        match="SECRET_KEY",
    ):
        settings._validate_required_fields(
            {
                "SECRET_KEY": None,
                "DB_HOST": "",
            },
        )


def test_validate_required_fields_accepts_complete_configuration() -> None:
    """
    It should accept a complete configuration.
    """

    settings = Settings(
        ENVIRONMENT=EnvironmentEnum.TESTING,
        LANGSMITH_TRACING=False,
        LANGSMITH_TRACING_V2=False,
    )

    settings._validate_required_fields(
        {
            "SECRET_KEY": "secret",
            "DB_HOST": "localhost",
        },
    )


def test_get_settings_returns_cached_instance() -> None:
    """
    It should return the cached settings instance.
    """

    get_settings.cache_clear()

    settings1 = get_settings()
    settings2 = get_settings()

    assert settings1 is settings2
