"""
Chat request and response schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.core.enums import MessageRole


class ChatRequest(BaseModel):
    """
    Request payload for chatting with the assistant.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    conversation_id: str = Field(
        description="Conversation identifier.",
    )

    message: str = Field(
        min_length=1,
        max_length=10_000,
        description="User message.",
    )


class ConversationEventResponse(BaseModel):
    """
    Conversation event response.
    """

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        populate_by_name=True,
    )

    id: str

    conversation_id: str

    parent_event_id: str | None

    role: MessageRole

    content: str

    event_metadata: dict[str, Any] | None = Field(
        serialization_alias="metadata",
    )

    created_at: datetime


class ChatResponse(BaseModel):
    """
    Chat response.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    conversation_id: str

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
