"""
Unit tests for application settings.
"""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from config import (
    AppSettings,
    DatabaseSettings,
    LLMSettings,
    SecuritySettings,
    Settings,
    get_settings,
)
from core.enums import CacheBackendEnum, EnvironmentEnum


def test_settings_allows_testing_without_required_fields() -> None:
    """
    It should allow creating settings in the testing environment without
    requiring external configuration.
    """
    settings = Settings(
        app=AppSettings(ENVIRONMENT=EnvironmentEnum.TESTING),
        llm=LLMSettings(
            SEARXNG_BASE_URL="http://localhost:8080",
            LANGSMITH_TRACING=False,
            LANGSMITH_TRACING_V2=False,
        ),
        security=SecuritySettings(JWT_SECRET_KEY=SecretStr("test-secret")),
    )

    assert settings.app.is_testing is True


def test_settings_accepts_valid_port() -> None:
    """
    It should accept a valid port number.
    """
    settings = Settings(
        app=AppSettings(ENVIRONMENT=EnvironmentEnum.TESTING, PORT=8080),
        llm=LLMSettings(
            SEARXNG_BASE_URL="http://localhost:8080",
            LANGSMITH_TRACING=False,
            LANGSMITH_TRACING_V2=False,
        ),
        security=SecuritySettings(JWT_SECRET_KEY=SecretStr("test-secret")),
    )

    assert settings.app.PORT == 8080


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
    It should reject invalid port numbers in AppSettings.
    """
    with pytest.raises(ValidationError):
        AppSettings(
            ENVIRONMENT=EnvironmentEnum.TESTING,
            PORT=port,
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
    It should reject non-positive database configuration values in DatabaseSettings.
    """
    with pytest.raises(ValidationError):
        DatabaseSettings(**{field: 0})


def test_settings_rejects_invalid_cache_ttl() -> None:
    """
    It should reject a non-positive cache TTL in SecuritySettings.
    """
    with pytest.raises(ValidationError):
        SecuritySettings(
            JWT_SECRET_KEY=SecretStr("test-secret"),
            CACHE_TTL=0,
        )


def test_database_url_returns_test_database_url() -> None:
    """
    It should return the test database URL in the testing environment.
    """
    settings = Settings(
        app=AppSettings(ENVIRONMENT=EnvironmentEnum.TESTING),
        llm=LLMSettings(
            SEARXNG_BASE_URL="http://localhost:8080",
            LANGSMITH_TRACING=False,
            LANGSMITH_TRACING_V2=False,
        ),
        security=SecuritySettings(JWT_SECRET_KEY=SecretStr("test-secret")),
    )

    assert settings.database_url == settings.database.TEST_DATABASE_URL


def test_database_url_returns_postgres_url() -> None:
    """
    It should build the PostgreSQL connection URL.
    """
    settings = Settings(
        app=AppSettings(ENVIRONMENT=EnvironmentEnum.DEVELOPMENT),
        database=DatabaseSettings(
            DB_HOST="localhost",
            DB_PORT=5432,
            DB_NAME="legal_ai",
            DB_USER="postgres",
            DB_PASSWORD="password",
        ),
        security=SecuritySettings(
            SECRET_KEY="secret",
            JWT_SECRET_KEY=SecretStr("jwt-secret"),
        ),
        llm=LLMSettings(
            SEARXNG_BASE_URL="http://localhost:8080",
            GROQ_API_KEY=SecretStr("api-key"),
            LANGSMITH_TRACING=False,
            LANGSMITH_TRACING_V2=False,
        ),
    )

    assert settings.async_database_url == (
        "postgresql+asyncpg://postgres:password@localhost:5432/legal_ai"
    )


def test_database_url_raises_for_production() -> None:
    """
    It should raise when requesting the async database URL in production.
    """
    settings = Settings(
        app=AppSettings(ENVIRONMENT=EnvironmentEnum.PRODUCTION),
        security=SecuritySettings(
            SECRET_KEY="secret",
            JWT_SECRET_KEY=SecretStr("jwt-secret"),
        ),
        llm=LLMSettings(
            SEARXNG_BASE_URL="http://localhost:8080",
            LANGSMITH_TRACING=False,
            LANGSMITH_TRACING_V2=False,
        ),
    )

    with pytest.raises(NotImplementedError):
        _ = settings.async_database_url


def test_alembic_database_url() -> None:
    """
    It should build the Alembic database URL.
    """
    settings = Settings(
        app=AppSettings(ENVIRONMENT=EnvironmentEnum.DEVELOPMENT),
        database=DatabaseSettings(
            DB_HOST="localhost",
            DB_PORT=5432,
            DB_NAME="legal_ai",
            DB_USER="postgres",
            DB_PASSWORD="password",
        ),
        security=SecuritySettings(
            SECRET_KEY="secret",
            JWT_SECRET_KEY=SecretStr("jwt-secret"),
        ),
        llm=LLMSettings(
            SEARXNG_BASE_URL="http://localhost:8080",
            GROQ_API_KEY=SecretStr("api-key"),
            LANGSMITH_TRACING=False,
            LANGSMITH_TRACING_V2=False,
        ),
    )

    assert settings.database_url == (
        "postgresql+psycopg://postgres:password@localhost:5432/legal_ai"
    )


def test_is_testing() -> None:
    """
    It should identify the testing environment.
    """
    settings = Settings(
        app=AppSettings(ENVIRONMENT=EnvironmentEnum.TESTING),
        llm=LLMSettings(
            SEARXNG_BASE_URL="http://localhost:8080",
            LANGSMITH_TRACING=False,
            LANGSMITH_TRACING_V2=False,
        ),
        security=SecuritySettings(JWT_SECRET_KEY=SecretStr("test-secret")),
    )

    assert settings.app.is_testing is True
    assert settings.app.is_development is False


def test_is_development() -> None:
    """
    It should identify the development environment.
    """
    settings = Settings(
        app=AppSettings(ENVIRONMENT=EnvironmentEnum.DEVELOPMENT),
        database=DatabaseSettings(
            DB_HOST="localhost",
            DB_NAME="legal_ai",
            DB_USER="postgres",
            DB_PASSWORD="password",
        ),
        security=SecuritySettings(
            SECRET_KEY="secret",
            JWT_SECRET_KEY=SecretStr("jwt-secret"),
        ),
        llm=LLMSettings(
            SEARXNG_BASE_URL="http://localhost:8080",
            GROQ_API_KEY=SecretStr("api-key"),
            LANGSMITH_TRACING=False,
            LANGSMITH_TRACING_V2=False,
        ),
    )

    assert settings.app.is_development is True
    assert settings.app.is_testing is False


def test_redis_enabled_when_using_redis() -> None:
    """
    It should report Redis as enabled.
    """
    settings = Settings(
        app=AppSettings(ENVIRONMENT=EnvironmentEnum.TESTING),
        security=SecuritySettings(
            JWT_SECRET_KEY=SecretStr("test-secret"),
            CACHE_BACKEND=CacheBackendEnum.REDIS,
        ),
        llm=LLMSettings(
            SEARXNG_BASE_URL="http://localhost:8080",
            LANGSMITH_TRACING=False,
            LANGSMITH_TRACING_V2=False,
        ),
    )

    assert settings.security.redis_enabled is True


def test_redis_disabled_when_using_memory_cache() -> None:
    """
    It should report Redis as disabled.
    """
    settings = Settings(
        app=AppSettings(ENVIRONMENT=EnvironmentEnum.TESTING),
        security=SecuritySettings(
            JWT_SECRET_KEY=SecretStr("test-secret"),
            CACHE_BACKEND=CacheBackendEnum.MEMORY,
        ),
        llm=LLMSettings(
            SEARXNG_BASE_URL="http://localhost:8080",
            LANGSMITH_TRACING=False,
            LANGSMITH_TRACING_V2=False,
        ),
    )

    assert settings.security.redis_enabled is False


def test_validate_configuration_requires_secret_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    It should require a secret key in the development environment.
    """
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(
            app=AppSettings(ENVIRONMENT=EnvironmentEnum.DEVELOPMENT),
            security=SecuritySettings(SECRET_KEY=None, JWT_SECRET_KEY=SecretStr("jwt-secret")),
            database=DatabaseSettings(
                DB_HOST="localhost",
                DB_NAME="legal_ai",
                DB_USER="postgres",
                DB_PASSWORD="password",
            ),
            llm=LLMSettings(
                SEARXNG_BASE_URL="http://localhost:8080",
                GROQ_API_KEY=SecretStr("api-key"),
            ),
        )


def test_validate_configuration_requires_database_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    It should require database configuration in the development environment.
    """
    monkeypatch.delenv("DB_HOST", raising=False)

    with pytest.raises(ValidationError, match="DB_HOST"):
        Settings(
            app=AppSettings(ENVIRONMENT=EnvironmentEnum.DEVELOPMENT),
            security=SecuritySettings(
                SECRET_KEY="secret",
                JWT_SECRET_KEY=SecretStr("jwt-secret"),
            ),
            database=DatabaseSettings(
                DB_HOST=None,
                DB_NAME="legal_ai",
                DB_USER="postgres",
                DB_PASSWORD="password",
            ),
            llm=LLMSettings(
                SEARXNG_BASE_URL="http://localhost:8080",
                GROQ_API_KEY=SecretStr("api-key"),
            ),
        )


def test_validate_configuration_requires_groq_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    It should require a Groq API key in the development environment.
    """
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    with pytest.raises(ValidationError, match="GROQ_API_KEY"):
        Settings(
            app=AppSettings(ENVIRONMENT=EnvironmentEnum.DEVELOPMENT),
            security=SecuritySettings(
                SECRET_KEY="secret",
                JWT_SECRET_KEY=SecretStr("jwt-secret"),
            ),
            database=DatabaseSettings(
                DB_HOST="localhost",
                DB_NAME="legal_ai",
                DB_USER="postgres",
                DB_PASSWORD="password",
            ),
            llm=LLMSettings(
                SEARXNG_BASE_URL="http://localhost:8080",
                GROQ_API_KEY=None,
            ),
        )


def test_validate_required_fields_raises() -> None:
    """
    It should raise when required fields are missing.
    """
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings._check_missing(
            {
                "SECRET_KEY": None,
                "DB_HOST": "",
            },
        )


def test_validate_required_fields_accepts_complete_configuration() -> None:
    """
    It should accept a complete configuration.
    """
    Settings._check_missing(
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
