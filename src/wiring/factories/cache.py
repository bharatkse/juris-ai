"""
Cache composition.

Single switch point between cache backends -- matches the existing
convention (see wiring.factories.evaluation.build_faithfulness_backend)
of one factory function deciding a settings-driven implementation
choice, rather than call sites branching on the setting themselves.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adapters.cache.base import AbstractCache
from adapters.cache.memory_cache import InMemoryLRUCache
from adapters.cache.redis_cache import RedisCache
from core.enums import CacheBackendEnum

if TYPE_CHECKING:
    from config.settings import Settings


def build_cache(*, settings: Settings) -> AbstractCache:
    """
    Build the configured AbstractCache implementation.

    REDIS (the default -- settings.security.CACHE_BACKEND) is the real
    path: durable across restarts, safe across multiple worker
    processes, and already a running, health-checked service (see
    deploy/docker/docker-compose.yml). MEMORY exists for local
    development without Docker and for tests -- it is per-process, not
    shared, and empties on restart.
    """

    if settings.security.CACHE_BACKEND is CacheBackendEnum.MEMORY:
        return InMemoryLRUCache(
            max_size=settings.security.CACHE_MAX_SIZE,
        )

    from redis.asyncio import Redis

    client = Redis.from_url(
        settings.security.REDIS_URL,
        decode_responses=True,
    )

    return RedisCache(client=client)
