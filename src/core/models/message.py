"""
Conversation message models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ConfigDict

from src.core.enums import MessageRole


class AgentMessage(BaseModel):
    """Represents an agent-to-agent request."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    sender: str

    recipient: str

    capability: str

    payload: dict[str, Any]


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
