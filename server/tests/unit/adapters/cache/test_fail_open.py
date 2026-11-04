"""
Unit tests: FailOpenCache (review R23).

The cache only saves work: query embeddings and judge scores are computed
when they aren't cached. So a backend that can't be reached must behave
like an empty cache, not fail the embedding or judge call that uses it.
Each failure logs a warning and counts in a metric; for a short while
after one, the backend isn't called at all, so an outage costs one
failed call per window, not one per lookup.
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.cache.fail_open import FailOpenCache

EMBED_KEY = "jurisai:cache:embed:v1:test-model:abc"
JUDGE_KEY = "jurisai:cache:judge:v1:groq:judge-model:def"


class _Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    record = MagicMock()
    monkeypatch.setattr("adapters.cache.fail_open.metrics.record_cache_unavailable", record)
    return record


def _cache(backend: MagicMock, clock: _Clock | None = None) -> FailOpenCache:
    return FailOpenCache(
        wrapped=backend,
        backend="redis",
        retry_after_s=30.0,
        clock=clock or _Clock(),
    )


def _down() -> MagicMock:
    backend = MagicMock()
    backend.get = AsyncMock(side_effect=ConnectionError("Error 111 connecting to localhost:6379."))
    backend.set = AsyncMock(side_effect=ConnectionError("Error 111 connecting to localhost:6379."))
    return backend


async def test_a_value_from_a_working_backend_is_returned() -> None:
    backend = MagicMock()
    backend.get = AsyncMock(return_value=[0.1, 0.2])
    backend.set = AsyncMock()

    cache = _cache(backend)

    assert await cache.get(EMBED_KEY) == [0.1, 0.2]
    await cache.set(EMBED_KEY, [0.1, 0.2], ttl=60)
    backend.set.assert_awaited_once_with(EMBED_KEY, [0.1, 0.2], ttl=60)


async def test_a_failed_read_is_a_miss_with_a_warning_and_a_metric(
    recorded: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    cache = _cache(_down())

    with caplog.at_level(logging.WARNING):
        assert await cache.get(EMBED_KEY) is None

    recorded.assert_called_once_with(
        backend="redis", cache="embedding", operation="get", outcome="error"
    )
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].error_type == "ConnectionError"
    # The key holds a hash of user text; never logged.
    assert EMBED_KEY not in caplog.text


async def test_a_failed_write_is_dropped(recorded: MagicMock) -> None:
    cache = _cache(_down())

    await cache.set(JUDGE_KEY, "0.92", ttl=60)

    recorded.assert_called_once_with(
        backend="redis", cache="judge", operation="set", outcome="error"
    )


async def test_after_a_failure_the_backend_is_skipped_until_the_retry_window_ends(
    recorded: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    clock = _Clock()
    backend = _down()
    cache = _cache(backend, clock)

    with caplog.at_level(logging.WARNING):
        await cache.get(EMBED_KEY)
        clock.now += 10
        assert await cache.get(EMBED_KEY) is None
        await cache.set(EMBED_KEY, [0.1], ttl=60)

    assert backend.get.await_count == 1
    backend.set.assert_not_awaited()
    assert recorded.call_args_list[1].kwargs == {
        "backend": "redis",
        "cache": "embedding",
        "operation": "get",
        "outcome": "skipped",
    }
    assert recorded.call_args_list[2].kwargs["outcome"] == "skipped"
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1


async def test_the_backend_is_tried_again_after_the_window_and_used_once_it_recovers(
    recorded: MagicMock,
) -> None:
    clock = _Clock()
    backend = _down()
    cache = _cache(backend, clock)

    await cache.get(EMBED_KEY)
    clock.now += 31
    backend.get = AsyncMock(return_value=[0.3])

    assert await cache.get(EMBED_KEY) == [0.3]
    clock.now += 1
    assert await cache.get(EMBED_KEY) == [0.3]
    assert backend.get.await_count == 2


async def test_a_key_outside_the_known_caches_is_labelled_other(recorded: MagicMock) -> None:
    cache = _cache(_down())

    await cache.get("something-else")

    assert recorded.call_args.kwargs["cache"] == "other"


async def test_maintenance_operations_still_raise() -> None:
    backend = MagicMock()
    backend.clear = AsyncMock(side_effect=ConnectionError("down"))
    backend.delete = AsyncMock(side_effect=ConnectionError("down"))

    cache = _cache(backend)

    with pytest.raises(ConnectionError):
        await cache.clear()
    with pytest.raises(ConnectionError):
        await cache.delete(EMBED_KEY)
