"""
Conversation models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .message import Message


@dataclass(slots=True, frozen=True)
class Conversation:
    """
    Provider-independent conversation.
    """

    messages: tuple[
        Message,
        ...,
    ]

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )
