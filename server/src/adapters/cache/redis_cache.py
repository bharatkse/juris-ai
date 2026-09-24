"""
Redis-backed cache implementation.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from adapters.cache.base import AbstractCache

if TYPE_CHECKING:
    from redis.asyncio import Redis


class RedisCache(AbstractCache):
    """
    Cache backed by a real Redis instance.

    Values are JSON-encoded -- round-trips floats exactly (Python's
    json module uses repr-based float formatting), so this is safe for
    both embedding vectors (list[float]) and judge response strings,
    the two things this cache exists for today.
    """

    def __init__(self, *, client: Redis) -> None:
        self._client = client

    async def get(self, key: str) -> Any | None:
        raw = await self._client.get(key)

        if raw is None:
            return None

        return json.loads(raw)

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        await self._client.set(
            key,
            json.dumps(value),
            ex=ttl,
        )

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def exists(self, key: str) -> bool:
        return bool(await self._client.exists(key))

    async def clear(self) -> None:
        """
        Flush the entire logical Redis database this client is
        connected to.

        Deliberately not scoped to this cache's own key prefix --
        nothing else uses this Redis instance today (confirmed: no
        other adapter in this codebase references Redis), so a full
        FLUSHDB is equivalent and far cheaper than a SCAN+DEL over a
        key pattern. Revisit if that ever changes.
        """

        await self._client.flushdb()

    async def size(self) -> int:
        return int(await self._client.dbsize())
