"""
Global pytest configuration.
"""

from __future__ import annotations

import os

import pytest

# ragas (imported transitively by rag.evaluation.faithfulness_backend,
# regardless of which FaithfulnessBackend is actually selected) starts
# a daemon analytics thread at import time and registers an atexit
# handler that flushes it via a real network POST. RAGAS_DO_NOT_TRACK
# is ragas' own sanctioned flag for this (see ragas/_analytics.py).
# This must run at module level, before collection imports any test
# module (and therefore before ragas itself) -- a per-test autouse
# fixture (e.g. via monkeypatch.setenv) runs too late (after
# collection has already imported ragas) and is reverted after each
# test, so it can't reliably cover the final atexit flush at session
# end. setdefault so an explicit override (e.g. deliberately testing
# analytics behavior) isn't clobbered.
os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")


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


# def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
#     try:
#         import ragas._analytics as analytics

#         batcher = analytics._analytics_batcher
#         batcher.shutdown()
#     except ImportError:
#         pass
