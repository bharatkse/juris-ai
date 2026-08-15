"""
Conversation message models.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class AgentMessageSchema(BaseModel):
    """Represents an agent-to-agent request."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    sender: str

    recipient: str

    capability: str

    payload: dict[str, Any]
