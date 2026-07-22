"""
Conversation request and response schemas.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Request Schemas
# =============================================================================


class CreateConversationRequest(BaseModel):
    """
    Request payload for creating a conversation.

    Currently empty.

    Reserved for future customization.
    """

    model_config = ConfigDict(
        extra="forbid",
    )


# =============================================================================
# Response Schemas
# =============================================================================


class ConversationResponse(BaseModel):
    """
    Conversation details.
    """

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    id: UUID

    title: str

    created_at: datetime

    updated_at: datetime


class ConversationCreatedResponse(BaseModel):
    """
    Response returned after creating a conversation.
    """

    conversation_id: UUID = Field(
        description="Conversation identifier.",
    )
