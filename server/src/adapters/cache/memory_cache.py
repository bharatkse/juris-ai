"""
In-process LRU cache implementation.

For local development without Redis running, or tests. Not safe to
rely on across multiple worker processes -- each process gets its own
independent cache with this backend (see RedisCache for the
multi-process-safe, durable-across-restarts option, which
CACHE_BACKEND defaults to).
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Any

from adapters.cache.base import AbstractCache


class InMemoryLRUCache(AbstractCache):
    """
    Simple size-bounded, TTL-respecting LRU cache.

    Eviction order is maintained by re-inserting a key on every
    get()/set() (moves it to the end of the OrderedDict) and popping
    from the front once max_size is exceeded.
    """

    def __init__(self, *, max_size: int = 1000) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be greater than zero.")

        self._max_size = max_size
        self._store: OrderedDict[str, tuple[Any, float | None]] = OrderedDict()

    async def get(self, key: str) -> Any | None:
        entry = self._store.get(key)

        if entry is None:
            return None

        value, expires_at = entry

        if expires_at is not None and expires_at <= time.monotonic():
            del self._store[key]
            return None

        self._store.move_to_end(key)

        return value

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        expires_at = time.monotonic() + ttl if ttl > 0 else None

        self._store[key] = (value, expires_at)
        self._store.move_to_end(key)

        while len(self._store) > self._max_size:
            self._store.popitem(last=False)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None

    async def clear(self) -> None:
        self._store.clear()

    async def size(self) -> int:
        return len(self._store)
