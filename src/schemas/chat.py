"""
Chat request and response schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.core.enums import MessageRole
from src.core.types import ConversationEventId, ConversationId


class ChatRequest(BaseModel):
    """
    Request payload for chatting with the assistant.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    conversation_id: ConversationId

    message: str = Field(
        min_length=1,
        max_length=10_000,
        description="User message.",
    )


class ConversationEventResponse(BaseModel):
    """
    Conversation event.
    """

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    id: ConversationEventId

    conversation_id: ConversationId

    parent_event_id: ConversationEventId | None

    role: MessageRole

    content: str

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        alias="event_metadata",
    )

    created_at: datetime


class AIResponse(BaseModel):
    """
    Assistant response.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    message: str

    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )


class ChatResponse(BaseModel):
    """
    Chat response.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    conversation_id: ConversationId

    response: AIResponse

    user_event: ConversationEventResponse

    assistant_event: ConversationEventResponse


class ChatStreamResponse(BaseModel):
    """
    Streamed chat response.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    content: str

    is_final: bool = False

    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )
