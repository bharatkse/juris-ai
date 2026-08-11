"""
Conversation models.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.core.enums import MessageRoleEnum


class ConversationMessageSchema(BaseModel):
    """
    Message used as conversation history during orchestration.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    role: MessageRoleEnum

    content: str
