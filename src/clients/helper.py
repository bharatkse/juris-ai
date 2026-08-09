"""
Shared client exception mapping helpers.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from src.core.logger import get_logger

log = get_logger(__name__)

T = TypeVar("T", bound=Exception)


def map_exception(
    *,
    exc: Exception,
    mappings: dict[
        type[Exception],
        Callable[[Exception], Exception],
    ],
    default: Callable[[Exception], Exception],
) -> Exception:
    """
    Map an infrastructure exception to a domain exception.
    """

    for exception_type, factory in mappings.items():
        if isinstance(
            exc,
            exception_type,
        ):
            log.debug(
                "Mapped exception '%s' to domain exception using '%s'.",
                type(exc).__name__,
                exception_type.__name__,
            )

            return factory(
                exc,
            )

    log.debug(
        "No exception mapping found for '%s'. Using default mapping.",
        type(exc).__name__,
    )

    return default(
        exc,
    )
