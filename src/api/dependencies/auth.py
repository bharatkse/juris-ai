"""
Authentication dependencies.

TODO:
    Replace with JWT authentication.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.types import UserId


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """
    Authenticated user.
    """

    id: UserId


#
# Development user.
#
# TODO:
# Replace once authentication is implemented.
#
_DEVELOPMENT_USER = CurrentUser(
    id=UserId("user_dev"),
)


async def get_current_user() -> CurrentUser:
    """
    Return the authenticated user.

    Currently returns a fixed development user until JWT
    authentication is implemented.
    """

    return _DEVELOPMENT_USER
