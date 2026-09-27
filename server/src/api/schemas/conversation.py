"""
Conversation request and response schemas.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from core.models.response import Page
from core.types import ConversationId, UserId


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
