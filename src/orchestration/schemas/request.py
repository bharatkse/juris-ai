"""
Incoming request models for the AI orchestrator.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.core.enums import AttachmentTypeEnum, RequestSourceEnum
from src.core.schemas.conversation import ConversationMessageSchema
from src.core.types import ConversationId, UserId


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

    type: AttachmentTypeEnum

    uri: str


class RequestMetadata(BaseModel):
    """
    Runtime request metadata.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    source: RequestSourceEnum = RequestSourceEnum.CHAT


class OrchestratorRequest(BaseModel):
    """
    Request accepted by the AI orchestrator.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )
    request_id: str

    conversation_id: ConversationId

    user_id: UserId

    message: str = Field(
        min_length=1,
        max_length=10_000,
    )

    history: list[ConversationMessageSchema] = Field(
        default_factory=list,
    )

    attachments: list[Attachment] = Field(
        default_factory=list,
    )

    metadata: RequestMetadata = Field(
        default_factory=RequestMetadata,
    )
