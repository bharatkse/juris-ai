"""
Conversation request and response schemas.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.core.types import ConversationId, UserId


class CreateConversationRequest(BaseModel):
    """
    Request payload for creating a conversation.

    Currently empty.

    Reserved for future customization.
    """

    model_config = ConfigDict(
        extra="forbid",
    )
    user_id: UserId = Field(
        ...,
        description="Identifier of the user creating the conversation.",
    )

    title: str | None = Field(
        default=None,
        description="Optional title for the conversation.",
    )


class ConversationResponse(BaseModel):
    """
    Conversation details.
    """

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    id: ConversationId
    user_id: UserId
    title: str

    created_at: datetime

    updated_at: datetime
