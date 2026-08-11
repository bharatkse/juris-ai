"""
Conversation request and response schemas.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.core.types import ConversationId, UserId
from src.schemas.base import Page


class CreateConversationRequest(BaseModel):
    """
    Request payload for creating a conversation.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Optional conversation title.",
    )


class UpdateConversationRequest(BaseModel):
    """
    Request payload for updating a conversation.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    title: str = Field(
        min_length=1,
        max_length=255,
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

    is_active: bool

    created_at: datetime

    updated_at: datetime


class ConversationListResponse(
    Page[ConversationResponse],
):
    """
    Paginated conversation response.
    """

    pass
