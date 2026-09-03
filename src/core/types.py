"""
Reusable application identifier types.

This module provides strongly typed identifier aliases used across the
application. All identifiers are represented as strings and validated
using a common prefixed-UUID format.
"""

from __future__ import annotations

from typing import Annotated, TypeAlias

from pydantic import Field


def _prefixed_id_field(
    prefix: str,
) -> Field:
    """
    Build the Pydantic field metadata for a prefixed identifier.

    The identifier must follow the format:

        {prefix}_{32 lowercase hexadecimal characters}

    Args:
        prefix: The required identifier prefix.

    Returns:
        Pydantic field metadata containing the validation pattern and
        identifier description.
    """

    return Field(
        pattern=rf"^{prefix}_[0-9a-f]{{32}}$",
        description=f"{prefix} identifier.",
    )


UserId: TypeAlias = Annotated[
    str,
    _prefixed_id_field("user"),
]
"""Unique identifier for a user."""


ConversationId: TypeAlias = Annotated[
    str,
    _prefixed_id_field("conv"),
]
"""Unique identifier for a conversation."""


ConversationEventId: TypeAlias = Annotated[
    str,
    _prefixed_id_field("evnt"),
]
"""Unique identifier for a conversation event."""


AgentActionId: TypeAlias = Annotated[
    str,
    _prefixed_id_field("actn"),
]
"""Unique identifier for an agent action."""


ApprovalId: TypeAlias = Annotated[
    str,
    _prefixed_id_field("appr"),
]
"""Unique identifier for an approval request."""


LibraryFileId: TypeAlias = Annotated[
    str,
    _prefixed_id_field("libf"),
]
"""Unique identifier for a library file."""


KnowledgeSourceId: TypeAlias = Annotated[
    str,
    _prefixed_id_field("ksrc"),
]
"""Unique identifier for a knowledge source."""


KnowledgeChunkId: TypeAlias = Annotated[
    str,
    _prefixed_id_field("kchn"),
]
"""Unique identifier for a knowledge chunk."""


KnowledgeEmbeddingId: TypeAlias = Annotated[
    str,
    _prefixed_id_field("kemb"),
]
"""Unique identifier for a knowledge embedding."""
