"""
Reusable application type aliases.
"""

from typing import Annotated

from pydantic import Field


def PrefixedId(prefix: str):
    """
    Return a reusable annotated string type for prefixed UUID identifiers.

    Example:
        UserId = PrefixedId("user")
        ConversationId = PrefixedId("conv")
    """
    return Annotated[
        str,
        Field(
            pattern=rf"^{prefix}_[0-9a-f]{{32}}$",
            description=f"{prefix} identifier.",
        ),
    ]


UserId = PrefixedId("user")
ConversationId = PrefixedId("conv")
