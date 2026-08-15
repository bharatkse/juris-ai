"""
Global pytest configuration.
"""

from __future__ import annotations

import pytest

pytest_plugins = [
    "tests.fixtures.environment",
    "tests.fixtures.faker",
    "tests.fixtures.database",
    "tests.fixtures.repositories",
    "tests.fixtures.agents",
    "tests.fixtures.services",
    "tests.fixtures.factories",
    "tests.fixtures.api",
    "tests.fixtures.clients.storage",
    "tests.fixtures.clients.llm",
    "tests.fixtures.clients.groq",
    "tests.fixtures.security",
    "tests.fixtures.orchestrator",
    "tests.fixtures.conversation",
    "tests.fixtures.planning",
]


@pytest.fixture(autouse=True)
def disable_langsmith(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Disable LangSmith tracing during unit tests.
    """

    monkeypatch.setenv(
        "LANGSMITH_TRACING",
        "false",
    )
    monkeypatch.setenv(
        "LANGSMITH_TRACING_V2",
        "false",
    )
