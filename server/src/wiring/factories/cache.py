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
from adapters.cache.fail_open import FailOpenCache
from adapters.cache.memory_cache import InMemoryLRUCache
from adapters.cache.redis_cache import RedisCache
from core.enums import CacheBackendEnum

if TYPE_CHECKING:
    from config.settings import Settings

# Redis is on the request path (query embeddings, judge scores) and answers
# in milliseconds; a Redis that doesn't answer within this is treated as
# down, and the cache fails open (review R23).
REDIS_SOCKET_TIMEOUT_S = 1.0


def build_cache(*, settings: Settings) -> AbstractCache:
    """
    Build the configured AbstractCache implementation.

    REDIS (the default -- settings.security.CACHE_BACKEND) is the real
    path: durable across restarts, safe across multiple worker
    processes, and already a running, health-checked service (see
    deploy/docker/docker-compose.yml). MEMORY exists for local
    development without Docker and for tests -- it is per-process, not
    shared, and empties on restart.

    The Redis cache fails open (FailOpenCache): an unreachable or slow
    Redis is treated as an empty cache, so embeddings and judge scores
    are computed instead of the calls failing (review R23).
    """

    if settings.security.CACHE_BACKEND is CacheBackendEnum.MEMORY:
        return InMemoryLRUCache(
            max_size=settings.security.CACHE_MAX_SIZE,
        )

    from redis.asyncio import Redis

    client = Redis.from_url(
        settings.security.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=REDIS_SOCKET_TIMEOUT_S,
        socket_timeout=REDIS_SOCKET_TIMEOUT_S,
    )

    return FailOpenCache(
        wrapped=RedisCache(client=client),
        backend="redis",
    )
