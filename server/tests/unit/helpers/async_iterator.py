"""
Async iterator helpers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TypeVar

T = TypeVar("T")


async def async_iterator(
    *items: T,
) -> AsyncIterator[T]:
    """
    Yield items as an async iterator.
    """

    for item in items:
        yield item
