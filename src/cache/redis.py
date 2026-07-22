"""
Redis-backed cache implementation.

This cache:
- Uses Redis for shared, distributed caching
- Supports TTL (time-to-live) expiration
- Serialises Python objects using pickle

Best suited for:
- Production deployments
- Multi-worker / multi-instance systems
- Distributed caching across services

Requirements:
    pip install redis

Notes:
- All keys are prefixed to avoid collisions with other applications
- Pickle allows caching of arbitrary Python objects (use carefully with trusted data)
"""

from __future__ import annotations

import pickle
from typing import Any

from src.cache.base import AbstractCache
from src.core.exceptions import CacheError
from src.core.logger import get_logger

logger = get_logger(__name__)


class RedisCache(AbstractCache):
    """
    Redis-based cache backend.

    Provides a shared cache across multiple processes or services.

    Parameters:
        url (str): Redis connection URL (e.g., redis://localhost:6379/0)
        default_ttl (int): Default TTL in seconds (0 = no expiration)
        prefix (str): Key prefix to avoid collisions
        socket_timeout (int): Redis socket timeout in seconds
    """

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        default_ttl: int = 3600,
        prefix: str = "legal_ai:",
        socket_timeout: int = 5,
    ) -> None:
        """
        Initialise Redis connection.

        - Validates connection immediately using ping()
        - Fails fast if Redis is unavailable
        """
        try:
            import redis

            # Create Redis client from URL
            self._redis = redis.from_url(
                url,
                socket_timeout=socket_timeout,
                decode_responses=False,  # keep raw bytes (we handle serialization)
            )

            # Test connection
            self._redis.ping()

        except ImportError as exc:
            raise CacheError("redis package required: pip install redis") from exc

        except Exception as exc:
            raise CacheError(f"Cannot connect to Redis at {url!r}: {exc}") from exc

        self._default_ttl = default_ttl
        self._prefix = prefix

        logger.info(f"RedisCache connected: {url!r} prefix={prefix!r}")

    def _key(self, key: str) -> str:
        """
        Apply prefix to cache key.

        Ensures isolation between applications sharing the same Redis instance.
        """
        return f"{self._prefix}{key}"

    @staticmethod
    def _serialise(value: Any) -> bytes:
        """
        Convert Python object → bytes.

        Uses pickle for flexibility (supports complex objects).
        """
        return pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def _deserialise(data: bytes) -> Any:
        """
        Convert bytes → Python object.
        """
        return pickle.loads(data)

    async def get(self, key: str) -> Any | None:
        """
        Retrieve value from Redis.

        Returns:
            Cached value or None if key not found or error occurs.
        """
        try:
            data = self._redis.get(self._key(key))

            if data is None:
                return None

            return self._deserialise(data)

        except Exception as exc:
            # Do NOT fail application if cache fails
            logger.warning(f"Redis GET failed for {key!r}: {exc}")
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """
        Store value in Redis.

        Behavior:
        - Uses default TTL if none provided
        - Uses SETEX if TTL > 0
        - Uses SET if no expiration required
        """
        effective_ttl = ttl if ttl is not None else self._default_ttl

        try:
            data = self._serialise(value)

            if effective_ttl > 0:
                # Set with expiration
                self._redis.setex(self._key(key), effective_ttl, data)
            else:
                # No expiration
                self._redis.set(self._key(key), data)

        except Exception as exc:
            logger.warning(f"Redis SET failed for {key!r}: {exc}")

    async def delete(self, key: str) -> None:
        """
        Delete a key from Redis.
        """
        try:
            self._redis.delete(self._key(key))
        except Exception as exc:
            logger.warning(f"Redis DEL failed for {key!r}: {exc}")

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in Redis.

        Returns:
            bool: True if key exists, else False
        """
        try:
            return bool(self._redis.exists(self._key(key)))
        except Exception:
            return False

    async def clear(self) -> None:
        """
        Clear all keys belonging to this application (based on prefix).

        Uses SCAN to avoid blocking Redis (safe for production).
        """
        try:
            pattern = f"{self._prefix}*"
            cursor = 0
            deleted = 0

            # Iterate over keys using SCAN (non-blocking)
            while True:
                cursor, keys = self._redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100,
                )

                if keys:
                    self._redis.delete(*keys)
                    deleted += len(keys)

                if cursor == 0:
                    break

            logger.info(f"RedisCache cleared {deleted} keys with prefix={self._prefix!r}")

        except Exception as exc:
            raise CacheError(f"Redis CLEAR failed: {exc}") from exc

    def size(self) -> int:
        """
        Estimate number of keys stored (based on prefix).

        Returns:
            int: Number of keys, or -1 if error occurs
        """
        try:
            pattern = f"{self._prefix}*"
            total = 0
            cursor = 0

            while True:
                cursor, keys = self._redis.scan(
                    cursor=cursor,
                    match=pattern,
                    count=100,
                )
                total += len(keys)

                if cursor == 0:
                    break

            return total

        except Exception:
            return -1
