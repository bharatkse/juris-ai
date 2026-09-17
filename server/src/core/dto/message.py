"""
Conversation message models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.enums import MessageRoleEnum


@dataclass(slots=True, frozen=True)
class MessageDTO:
    """
    Provider-independent conversation message.
    """

    role: MessageRoleEnum

    content: str

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )
