"""
Environment fixtures.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def clean_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Remove environment variables that may be loaded from the host or .env.
    """

    for key in [
        "SECRET_KEY",
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
        "GROQ_API_KEY",
        "SEARXNG_BASE_URL",
        "LANGSMITH_TRACING",
        "LANGSMITH_TRACING_V2",
        "LANGSMITH_API_KEY",
        "LANGSMITH_PROJECT",
        "LANGSMITH_ENDPOINT",
    ]:
        monkeypatch.delenv(
            key,
            raising=False,
        )
