"""
Unit tests for LangSmith observability configuration.
"""

from __future__ import annotations

import os

from src.core.config import Settings
from src.observability.langsmith import configure_langsmith


def test_configure_langsmith_disabled(
    monkeypatch,
) -> None:
    """
    LangSmith environment variables are not configured
    when tracing is disabled.
    """
    monkeypatch.delenv(
        "LANGSMITH_TRACING",
        raising=False,
    )
    monkeypatch.delenv(
        "LANGSMITH_TRACING_V2",
        raising=False,
    )
    monkeypatch.delenv(
        "LANGSMITH_ENDPOINT",
        raising=False,
    )
    monkeypatch.delenv(
        "LANGSMITH_PROJECT",
        raising=False,
    )
    monkeypatch.delenv(
        "LANGSMITH_API_KEY",
        raising=False,
    )

    settings = Settings(
        LANGSMITH_TRACING=False,
    )

    configure_langsmith(
        settings=settings,
    )

    assert os.getenv("LANGSMITH_TRACING") is None
    assert os.getenv("LANGSMITH_TRACING_V2") is None
    assert os.getenv("LANGSMITH_ENDPOINT") is None
    assert os.getenv("LANGSMITH_PROJECT") is None
    assert os.getenv("LANGSMITH_API_KEY") is None


def test_configure_langsmith_enabled(
    monkeypatch,
) -> None:
    """
    LangSmith environment variables are configured
    when tracing is enabled.
    """
    settings = Settings(
        LANGSMITH_TRACING=True,
        LANGSMITH_ENDPOINT="https://api.smith.langchain.com",
        LANGSMITH_PROJECT="juris-ai-test",
        LANGSMITH_API_KEY="test-api-key",
    )

    configure_langsmith(
        settings=settings,
    )

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_TRACING_V2"] == "true"
    assert os.environ["LANGSMITH_ENDPOINT"] == "https://api.smith.langchain.com"
    assert os.environ["LANGSMITH_PROJECT"] == "juris-ai-test"
    assert os.environ["LANGSMITH_API_KEY"] == "test-api-key"


def test_configure_langsmith_overwrites_existing_environment(
    monkeypatch,
) -> None:
    """
    LangSmith configuration replaces existing environment values
    when tracing is enabled.
    """
    monkeypatch.setenv(
        "LANGSMITH_TRACING",
        "false",
    )
    monkeypatch.setenv(
        "LANGSMITH_TRACING_V2",
        "false",
    )
    monkeypatch.setenv(
        "LANGSMITH_ENDPOINT",
        "https://old.example.com",
    )
    monkeypatch.setenv(
        "LANGSMITH_PROJECT",
        "old-project",
    )
    monkeypatch.setenv(
        "LANGSMITH_API_KEY",
        "old-api-key",
    )

    settings = Settings(
        LANGSMITH_TRACING=True,
        LANGSMITH_ENDPOINT="https://api.smith.langchain.com",
        LANGSMITH_PROJECT="juris-ai-test",
        LANGSMITH_API_KEY="new-api-key",
    )

    configure_langsmith(
        settings=settings,
    )

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_TRACING_V2"] == "true"
    assert os.environ["LANGSMITH_ENDPOINT"] == "https://api.smith.langchain.com"
    assert os.environ["LANGSMITH_PROJECT"] == "juris-ai-test"
    assert os.environ["LANGSMITH_API_KEY"] == "new-api-key"
