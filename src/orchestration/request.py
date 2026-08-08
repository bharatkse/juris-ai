"""
Incoming request models for the AI orchestrator.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from src.core.enums import MessageRole
from src.core.types import ConversationId, UserId


class AttachmentType(StrEnum):
    """
    Supported attachment types.
    """

    PDF = "pdf"
    DOCX = "docx"
    IMAGE = "image"
    TEXT = "text"
    OTHER = "other"


class RequestSource(StrEnum):
    """
    Source of the orchestration request.
    """

    CHAT = "chat"
    API = "api"
    TOOL = "tool"


class Attachment(BaseModel):
    """
    Uploaded attachment available during execution.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    id: str

    name: str

    type: AttachmentType

    uri: str


class ConversationMessage(BaseModel):
    """
    Conversation history message.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    role: MessageRole

    content: str


class RequestMetadata(BaseModel):
    """
    Runtime request metadata.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    source: RequestSource = RequestSource.CHAT


class OrchestratorRequest(BaseModel):
    """
    Request accepted by the AI orchestrator.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    conversation_id: ConversationId

    user_id: UserId

    message: str = Field(
        min_length=1,
        max_length=10_000,
    )

    history: list[ConversationMessage] = Field(
        default_factory=list,
    )

    attachments: list[Attachment] = Field(
        default_factory=list,
    )

    metadata: RequestMetadata = Field(
        default_factory=RequestMetadata,
    )
