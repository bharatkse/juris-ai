"""
Conversation models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .message import MessageDTO


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
