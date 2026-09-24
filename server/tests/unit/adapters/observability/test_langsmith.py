"""
Unit tests for LangSmith observability configuration.
"""

from __future__ import annotations

import os

import pytest
from pydantic import SecretStr

from adapters.observability.langsmith import configure_langsmith
from config import AppSettings, LLMSettings, SecuritySettings, Settings
from core.enums import EnvironmentEnum


@pytest.fixture(autouse=True)
def clean_langsmith_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure environment variables are clean before and after each test."""
    env_vars = [
        "LANGSMITH_TRACING",
        "LANGSMITH_TRACING_V2",
        "LANGSMITH_ENDPOINT",
        "LANGSMITH_PROJECT",
        "LANGSMITH_API_KEY",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)


def _build_test_settings(
    *,
    tracing: bool = False,
    endpoint: str = "https://api.smith.langchain.com",
    project: str = "juris-ai",
    api_key: str | None = None,
) -> Settings:
    """Helper to construct Settings with proper modular sub-models."""
    return Settings(
        app=AppSettings(ENVIRONMENT=EnvironmentEnum.TESTING),
        security=SecuritySettings(JWT_SECRET_KEY=SecretStr("test-secret")),
        llm=LLMSettings(
            SEARXNG_BASE_URL="http://localhost:8080",
            LANGSMITH_TRACING=tracing,
            LANGSMITH_TRACING_V2=tracing,
            LANGSMITH_ENDPOINT=endpoint,
            LANGSMITH_PROJECT=project,
            LANGSMITH_API_KEY=SecretStr(api_key) if api_key else None,
        ),
    )


def test_configure_langsmith_disabled() -> None:
    """
    LangSmith environment variables are not configured
    when tracing is disabled.
    """
    settings = _build_test_settings(tracing=False)

    configure_langsmith(settings=settings)

    assert os.getenv("LANGSMITH_TRACING") is None
    assert os.getenv("LANGSMITH_TRACING_V2") is None
    assert os.getenv("LANGSMITH_ENDPOINT") is None
    assert os.getenv("LANGSMITH_PROJECT") is None
    assert os.getenv("LANGSMITH_API_KEY") is None


def test_configure_langsmith_enabled() -> None:
    """
    LangSmith environment variables are configured
    when tracing is enabled.
    """
    settings = _build_test_settings(
        tracing=True,
        endpoint="https://api.smith.langchain.com",
        project="juris-ai-test",
        api_key="test-api-key",
    )

    configure_langsmith(settings=settings)

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_TRACING_V2"] == "true"
    assert os.environ["LANGSMITH_ENDPOINT"] == "https://api.smith.langchain.com"
    assert os.environ["LANGSMITH_PROJECT"] == "juris-ai-test"
    assert os.environ["LANGSMITH_API_KEY"] == "test-api-key"


def test_configure_langsmith_overwrites_existing_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    LangSmith configuration replaces existing environment values
    when tracing is enabled.
    """
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGSMITH_TRACING_V2", "false")
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://old.example.com")
    monkeypatch.setenv("LANGSMITH_PROJECT", "old-project")
    monkeypatch.setenv("LANGSMITH_API_KEY", "old-api-key")

    settings = _build_test_settings(
        tracing=True,
        endpoint="https://api.smith.langchain.com",
        project="juris-ai-test",
        api_key="new-api-key",
    )

    configure_langsmith(settings=settings)

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_TRACING_V2"] == "true"
    assert os.environ["LANGSMITH_ENDPOINT"] == "https://api.smith.langchain.com"
    assert os.environ["LANGSMITH_PROJECT"] == "juris-ai-test"
    assert os.environ["LANGSMITH_API_KEY"] == "new-api-key"
