"""
CacheManager builds and returns the correct cache backend based on
settings.CACHE_BACKEND, and provides convenience helpers with
domain-specific key prefixes.
"""

from __future__ import annotations

import hashlib
from typing import Any

from src.cache.base import AbstractCache
from src.core.config import settings
from src.core.constants import (
    CACHE_PREFIX_DOCUMENT,
    CACHE_PREFIX_GENERATE,
    CACHE_PREFIX_SEARCH,
)
from src.core.logger import get_logger

log = get_logger(__name__)


def build_cache() -> AbstractCache:
    """
    Factory — returns the configured cache backend singleton.
    Called once at startup from the DI container.
    """
    backend = settings.CACHE_BACKEND.lower()

    if backend == "redis":
        from src.cache.redis import RedisCache

        return RedisCache(
            url=settings.REDIS_URL,
            default_ttl=settings.CACHE_TTL,
        )

    # Default: in-memory
    from src.cache.memory import MemoryCache

    return MemoryCache(
        max_size=settings.CACHE_MAX_SIZE,
        default_ttl=settings.CACHE_TTL,
    )


class CacheManager:
    """
    Thin wrapper around AbstractCache that:
    - Adds domain-specific key prefixes
    - Serialises / deserialises cache keys from query params
    - Provides typed get/set helpers for search and generation results
    """

    def __init__(self, cache: AbstractCache) -> None:
        self._cache = cache

    # ── Generic helpers ──
    async def get(self, key: str) -> Any | None:
        return await self._cache.get(key)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        await self._cache.set(key, value, ttl=ttl or settings.CACHE_TTL)

    async def delete(self, key: str) -> None:
        await self._cache.delete(key)

    async def clear(self) -> None:
        await self._cache.clear()

    def size(self) -> int:
        return self._cache.size()

    # ── Domain-specific helpers ────
    @staticmethod
    def search_key(query: str, top_k: int) -> str:
        digest = hashlib.md5(f"{query}:{top_k}".encode()).hexdigest()
        return f"{CACHE_PREFIX_SEARCH}{digest}"

    @staticmethod
    def generate_key(query: str, top_k: int) -> str:
        digest = hashlib.md5(f"{query}:{top_k}".encode()).hexdigest()
        return f"{CACHE_PREFIX_GENERATE}{digest}"

    @staticmethod
    def document_key(document_id: str) -> str:
        return f"{CACHE_PREFIX_DOCUMENT}{document_id}"

    async def get_search(self, query: str, top_k: int) -> Any | None:
        return await self._cache.get(self.search_key(query, top_k))

    async def set_search(self, query: str, top_k: int, value: Any) -> None:
        await self._cache.set(self.search_key(query, top_k), value)

    async def get_generate(self, query: str, top_k: int) -> Any | None:
        return await self._cache.get(self.generate_key(query, top_k))

    async def set_generate(self, query: str, top_k: int, value: Any) -> None:
        await self._cache.set(self.generate_key(query, top_k), value)

    async def invalidate_document(self, document_id: str) -> None:
        """Invalidate any cached data for a specific document."""
        await self._cache.delete(self.document_key(document_id))
        log.debug(f"Cache invalidated for document {document_id!r}")

    def stats(self) -> dict:
        base: dict = {"size": self.size(), "backend": settings.CACHE_BACKEND}
        if hasattr(self._cache, "stats"):
            base.update(self._cache.stats())
        return base
