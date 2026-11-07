"""
Fail-open cache decorator (review R23).

The cache only saves work: query embeddings and judge scores are computed
whenever they aren't cached. So a backend that can't be reached (Redis
down, a timeout, a value that won't decode) must behave like an empty
cache. Before this wrapper, a Redis outage failed every embedding call,
which silently turned retrieval into keyword-only search and made the
answer gate unable to score any answer.

get() and set() fail open: a failure is a miss (or a dropped write),
logged as a warning with the error type (never the key, which holds a
hash of user text) and counted in juris_ai_cache_unavailable_total. After
a failure the backend is skipped for retry_after_s, so an outage costs one
failed call per window instead of one per lookup, and logs one warning per
window. The first call after the window tries the backend again.

delete(), exists(), clear() and size() are maintenance operations, not on
any request path, so their errors still propagate.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Literal

from adapters.cache.base import AbstractCache
from adapters.observability.logger import get_logger
from adapters.observability.metrics import metrics

logger = get_logger(__name__)

DEFAULT_RETRY_AFTER_S = 30.0

# Key prefixes of the caches that share the backend (CachingEmbeddingProvider,
# the LLM judge in wiring/factories/evaluation.py), for the metric label.
_CACHE_NAMES = {
    "jurisai:cache:embed:": "embedding",
    "jurisai:cache:judge:": "judge",
}


def _cache_name(key: str) -> str:
    for prefix, name in _CACHE_NAMES.items():
        if key.startswith(prefix):
            return name
    return "other"


class FailOpenCache(AbstractCache):
    """
    An AbstractCache whose reads and writes never raise.
    """

    def __init__(
        self,
        *,
        wrapped: AbstractCache,
        backend: str,
        retry_after_s: float = DEFAULT_RETRY_AFTER_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.wrapped = wrapped
        self._backend = backend
        self._retry_after_s = retry_after_s
        self._clock = clock
        self._skip_until: float | None = None

    async def get(self, key: str) -> Any | None:
        if self._skipping(key, "get"):
            return None

        try:
            return await self.wrapped.get(key)
        except Exception as exc:
            self._failed(key, "get", exc)
            return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        if self._skipping(key, "set"):
            return

        try:
            await self.wrapped.set(key, value, ttl=ttl)
        except Exception as exc:
            self._failed(key, "set", exc)

    async def delete(self, key: str) -> None:
        await self.wrapped.delete(key)

    async def exists(self, key: str) -> bool:
        return await self.wrapped.exists(key)

    async def clear(self) -> None:
        await self.wrapped.clear()

    async def size(self) -> int:
        return await self.wrapped.size()

    def _skipping(self, key: str, operation: Literal["get", "set"]) -> bool:
        if self._skip_until is None:
            return False

        if self._clock() >= self._skip_until:
            self._skip_until = None
            return False

        metrics.record_cache_unavailable(
            backend=self._backend,
            cache=_cache_name(key),
            operation=operation,
            outcome="skipped",
        )
        return True

    def _failed(self, key: str, operation: Literal["get", "set"], exc: Exception) -> None:
        cache = _cache_name(key)

        metrics.record_cache_unavailable(
            backend=self._backend,
            cache=cache,
            operation=operation,
            outcome="error",
        )

        logger.warning(
            "Cache unavailable; continuing without it for %.0f s.",
            self._retry_after_s,
            extra={
                "operation": "cache_fail_open",
                "backend": self._backend,
                "cache": cache,
                "cache_operation": operation,
                "error_type": type(exc).__name__,
            },
        )

        self._skip_until = self._clock() + self._retry_after_s
