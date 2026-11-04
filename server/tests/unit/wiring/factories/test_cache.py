"""
Unit tests: build_cache().

The Redis cache is wrapped so that an unreachable Redis behaves like an
empty cache (review R23), and its client gets short socket timeouts, so
a Redis that hangs can't stall a request either.
"""

from __future__ import annotations

from types import SimpleNamespace

from adapters.cache.fail_open import FailOpenCache
from adapters.cache.memory_cache import InMemoryLRUCache
from adapters.cache.redis_cache import RedisCache
from core.enums import CacheBackendEnum
from wiring.factories.cache import REDIS_SOCKET_TIMEOUT_S, build_cache


def _settings(backend: CacheBackendEnum) -> SimpleNamespace:
    return SimpleNamespace(
        security=SimpleNamespace(
            CACHE_BACKEND=backend,
            CACHE_MAX_SIZE=10,
            REDIS_URL="redis://localhost:6379/0",
        )
    )


def test_the_redis_cache_fails_open() -> None:
    cache = build_cache(settings=_settings(CacheBackendEnum.REDIS))

    assert isinstance(cache, FailOpenCache)
    assert isinstance(cache.wrapped, RedisCache)


def test_the_redis_client_has_short_timeouts() -> None:
    cache = build_cache(settings=_settings(CacheBackendEnum.REDIS))

    kwargs = cache.wrapped._client.connection_pool.connection_kwargs
    assert kwargs["socket_timeout"] == REDIS_SOCKET_TIMEOUT_S
    assert kwargs["socket_connect_timeout"] == REDIS_SOCKET_TIMEOUT_S
    assert 0 < REDIS_SOCKET_TIMEOUT_S <= 2


def test_the_in_memory_cache_is_not_wrapped() -> None:
    cache = build_cache(settings=_settings(CacheBackendEnum.MEMORY))

    assert isinstance(cache, InMemoryLRUCache)
