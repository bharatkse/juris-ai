"""
In-memory LRU cache with TTL (time-to-live) support.

This cache is:
- Thread-safe (uses a Lock)
- Size-bounded (LRU eviction policy)
- TTL-aware (entries expire automatically on access)

Best suited for:
- Development environments
- Single-instance deployments
- Lightweight caching (e.g., embeddings, API responses)

Not suitable for:
- Multi-instance distributed systems (use Redis instead)
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from typing import Any

from src.cache.base import AbstractCache
from src.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class _Entry:
    """
    Internal cache entry representation.

    Attributes:
        value: Cached object
        expires_at: Expiration timestamp (monotonic time).
                    0 means the entry never expires.
    """

    value: Any
    expires_at: float


class MemoryCache(AbstractCache):
    """
    Thread-safe in-memory cache with LRU eviction and TTL support.

    Design:
    - Uses OrderedDict to maintain insertion/access order
    - Oldest (least recently used) items are evicted first
    - TTL is checked lazily (on access)

    Parameters:
        max_size (int): Maximum number of cache entries
        default_ttl (int): Default expiration time in seconds
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600) -> None:
        # OrderedDict maintains order of insertion/access (for LRU)
        self._store: OrderedDict[str, _Entry] = OrderedDict()

        # Lock ensures thread safety across concurrent access
        self._lock = Lock()

        self._max_size = max_size
        self._default_ttl = default_ttl

        # Metrics (useful for observability/debugging)
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Any | None:
        """
        Retrieve value from cache.

        Behavior:
        - Returns None if key not found or expired
        - Moves accessed key to end (LRU behavior)
        """
        with self._lock:
            entry = self._store.get(key)

            # Cache miss
            if entry is None:
                self._misses += 1
                return None

            # Check expiration
            if entry.expires_at and time.monotonic() > entry.expires_at:
                del self._store[key]
                self._misses += 1
                return None

            # Mark as recently used
            self._store.move_to_end(key)

            self._hits += 1
            return entry.value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """
        Store value in cache.

        - Updates existing key OR inserts new one
        - Evicts least-recently-used item if max_size exceeded
        - Applies TTL (default or custom)
        """
        effective_ttl = ttl if ttl is not None else self._default_ttl
        expires_at = time.monotonic() + effective_ttl if effective_ttl > 0 else 0.0

        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)

            elif len(self._store) >= self._max_size:
                oldest_key, _ = self._store.popitem(last=False)
                logger.debug(f"Cache evicted LRU key: {oldest_key!r}")

            self._store[key] = _Entry(value=value, expires_at=expires_at)

    async def delete(self, key: str) -> None:
        """Remove a key from cache."""
        with self._lock:
            self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        return (await self.get(key)) is not None

    async def clear(self) -> None:
        """Clear cache and reset metrics."""
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

        logger.info("MemoryCache cleared")

    def size(self) -> int:
        """Return current cache size."""
        with self._lock:
            return len(self._store)

    def stats(self) -> dict:
        """Return cache performance metrics."""
        total = self._hits + self._misses

        return {
            "size": self.size(),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 3) if total else 0.0,
        }
