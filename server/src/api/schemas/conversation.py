"""
Conversation request and response schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from agentic.orchestration.schemas.response import Citation, Source
from core.enums import MessageRoleEnum
from core.models.response import Page
from core.types import ConversationEventId, ConversationId, UserId

if TYPE_CHECKING:
    from adapters.persistence.sqlalchemy.models.conversation_event import (
        ConversationEvent,
    )


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

    memory_disabled: bool = Field(
        default=False,
        description=(
            'True when "don\'t remember this" is on for this conversation: '
            "nothing said from now on is saved to long-term memory. Forward-only "
            "-- facts already saved are not removed by turning it on."
        ),
    )

    created_at: datetime

    updated_at: datetime


class ConversationListResponse(
    Page[ConversationResponse],
):
    """
    Paginated conversation response.
    """

    pass


class ConversationMessageResponse(BaseModel):
    """
    A message stored in a conversation: a user's message or an
    assistant's answer, including an answer saved after an approval
    was decided.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    id: ConversationEventId

    conversation_id: ConversationId

    parent_event_id: ConversationEventId | None = Field(
        description=(
            "The user message an assistant answer replies to, including an "
            "answer saved after an approval. Absent for a user message."
        ),
    )

    role: MessageRoleEnum

    content: str

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "What was stored with the message. An assistant answer carries the "
            "agents and workflow that produced it, plus `approval` when it asked "
            "for one and `guardrail` when a guardrail acted. An answer saved "
            "after an approval carries `resumed_agent_action_id`."
        ),
    )

    citations: list[Citation] = Field(
        default_factory=list,
    )

    sources: list[Source] = Field(
        default_factory=list,
    )

    created_at: datetime

    @classmethod
    def from_event(
        cls,
        event: ConversationEvent,
    ) -> ConversationMessageResponse:
        """
        Build the response from a stored conversation event, whose
        ``citations`` column holds {"citations": [...], "sources": [...]}
        or None.
        """

        stored = event.citations or {}

        return cls(
            id=event.id,
            conversation_id=event.conversation_id,
            parent_event_id=event.parent_event_id,
            role=event.role,
            content=event.content,
            metadata=event.event_metadata or {},
            citations=stored.get("citations") or [],
            sources=stored.get("sources") or [],
            created_at=event.created_at,
        )


class ConversationMessageListResponse(
    Page[ConversationMessageResponse],
):
    """
    Paginated conversation messages.
    """

    pass


class UpdateConversationMemoryRequest(BaseModel):
    """
    Request payload for the per-conversation "don't remember this" switch.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    memory_disabled: bool = Field(
        description=(
            "True: stop saving anything said in this conversation to long-term "
            "memory from now on. False: allow it again (subject to the account-level "
            "memory setting). This is forward-only -- it does NOT delete facts "
            "already saved from earlier messages; delete those from the memory "
            "list or turn memory off to delete everything."
        ),
    )
