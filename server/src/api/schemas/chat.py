"""
Chat request and response schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import File, Form, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from agentic.orchestration.schemas.response import (
    Citation,
    ResponseMetadata,
    Source,
    Usage,
)
from core.enums import MessageRoleEnum
from core.types import ConversationEventId, ConversationId


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

    files: list[UploadFile] = Field(
        default_factory=list,
        description="Documents attached to the chat message.",
    )

    @classmethod
    def as_form(
        cls,
        conversation_id: ConversationId = Form(...),
        message: str = Form(...),
        files: list[UploadFile] = File(default=[]),
    ) -> ChatRequest:
        return cls(
            conversation_id=conversation_id,
            message=message,
            files=files,
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

    role: MessageRoleEnum

    content: str

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        alias="event_metadata",
    )

    created_at: datetime


class AIResponse(BaseModel):
    """
    Assistant response returned by the chat API.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    content: str

    citations: list[Citation] = Field(
        default_factory=list,
    )

    sources: list[Source] = Field(
        default_factory=list,
    )

    usage: Usage = Field(
        default_factory=Usage,
    )

    metadata: ResponseMetadata = Field(
        default_factory=ResponseMetadata,
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
