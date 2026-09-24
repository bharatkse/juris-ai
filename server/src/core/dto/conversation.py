"""
Conversation models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .message import MessageDTO
from .user_memory import UserMemoryContextItem


@dataclass(slots=True, frozen=True)
class ConversationDTO:
    """
    Provider-independent conversation.
    """

    messages: tuple[
        MessageDTO,
        ...,
    ]

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )

    # Saved user memories selected for this turn. Kept out of
    # ``messages`` on purpose: prompt builders render it as its own
    # block and reserve its tokens with the system prompt, whereas
    # ``messages`` is trimmed oldest-first under token pressure.
    user_memory: tuple[UserMemoryContextItem, ...] = ()
