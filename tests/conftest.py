"""
Global pytest configuration.
"""

from __future__ import annotations

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = str(item.path)

        if "/tests/unit/" in path:
            item.add_marker(pytest.mark.unit)

        elif "/tests/smoke/" in path:
            item.add_marker(pytest.mark.smoke)


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
