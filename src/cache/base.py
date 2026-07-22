"""
Abstract cache interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AbstractCache(ABC):
    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Return cached value or None."""

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Store value with a TTL in seconds."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove a key."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists (without fetching value)."""

    @abstractmethod
    async def clear(self) -> None:
        """Remove all keys."""

    @abstractmethod
    def size(self) -> int:
        """Number of currently cached items."""
