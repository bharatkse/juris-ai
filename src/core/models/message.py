"""
Conversation message models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.enums import MessageRole


@dataclass(slots=True, frozen=True)
class Message:
    """
    Provider-independent conversation message.
    """

    role: MessageRole

    content: str

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )
