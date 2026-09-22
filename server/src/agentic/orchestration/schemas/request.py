"""
Incoming request models for the AI orchestrator.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from core.dto.user_memory import UserMemoryContextItem
from core.enums import AttachmentTypeEnum, RequestSourceEnum
from core.models.conversation import ConversationMessageSchema
from core.types import ConversationEventId, ConversationId, UserId


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

    request_id: UUID

    conversation_id: ConversationId
    current_event_id: ConversationEventId
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

    # The user's saved memories selected for this turn (empty unless the
    # user opted in and this conversation's "don't remember this" switch
    # is off). Deliberately separate from ``history``: history is trimmed
    # oldest-first under token pressure, memory must not be.
    user_memory: tuple[UserMemoryContextItem, ...] = ()

    metadata: RequestMetadata = Field(
        default_factory=RequestMetadata,
    )
