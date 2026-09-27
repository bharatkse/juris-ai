"""
Reusable application identifier types.

This module provides strongly typed identifier aliases used across the
application. All identifiers are represented as strings and validated
using a common prefixed-UUID format.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, TypeAlias

from pydantic import Field


def prefixed_id_field(prefix: str) -> str:
    """
    Generate a prefixed identifier.

    Returns:
        Identifier in the format:
        {prefix}_{32 lowercase hexadecimal characters}.
    """

    return f"{prefix}_{uuid.uuid4().hex}"


def prefixed_id_validator(prefix: str) -> Any:
    """
    Build Pydantic field metadata for a prefixed identifier.
    """

    return Field(
        pattern=rf"^{prefix}_[0-9a-f]{{32}}$",
        description=f"{prefix} identifier.",
    )


UserId: TypeAlias = Annotated[
    str,
    prefixed_id_validator("user"),
]

ConversationId: TypeAlias = Annotated[
    str,
    prefixed_id_validator("conv"),
]

ConversationEventId: TypeAlias = Annotated[
    str,
    prefixed_id_validator("evnt"),
]

AgentActionId: TypeAlias = Annotated[
    str,
    prefixed_id_validator("actn"),
]

ApprovalId: TypeAlias = Annotated[
    str,
    prefixed_id_validator("appr"),
]

LibraryId: TypeAlias = Annotated[
    str,
    prefixed_id_validator("liby"),
]

KnowledgeSourceId: TypeAlias = Annotated[
    str,
    prefixed_id_validator("ksrc"),
]

KnowledgeChunkId: TypeAlias = Annotated[
    str,
    prefixed_id_validator("kchn"),
]

KnowledgeEmbeddingId: TypeAlias = Annotated[
    str,
    prefixed_id_validator("kemb"),
]

UserMemoryId: TypeAlias = Annotated[
    str,
    prefixed_id_validator("umem"),
]
