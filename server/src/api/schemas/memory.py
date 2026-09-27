"""
User memory request and response schemas.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from core.enums import UserMemoryKindEnum, UserMemoryStatusEnum
from core.models.response import Page
from core.types import ConversationId, UserMemoryId


class UpdateMemorySettingsRequest(BaseModel):
    """
    Request payload for turning long-term memory on or off.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    enabled: bool = Field(
        description=(
            "True: allow the assistant to save short, durable facts you state "
            "(preferences, profile details) and use them in later conversations. "
            "False: stop, AND permanently delete every memory saved so far. "
            "Turning it off cannot be undone."
        ),
    )


class MemorySettingsResponse(BaseModel):
    """
    The user's account-level memory setting.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    enabled: bool = Field(
        description="Whether long-term memory is on. Off unless the user turned it on.",
    )

    consent_updated_at: datetime | None = Field(
        default=None,
        description="When this setting last changed. Null if it never has.",
    )


class MemoryItemResponse(BaseModel):
    """
    One saved memory, as shown to the user who owns it.
    """

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    id: UserMemoryId

    kind: UserMemoryKindEnum

    content: str

    status: UserMemoryStatusEnum

    confidence: float

    source_conversation_id: ConversationId | None = None

    last_used_at: datetime

    expires_at: datetime | None = None

    created_at: datetime


class MemoryListResponse(
    Page[MemoryItemResponse],
):
    """
    Paginated list of the user's saved memories.
    """

    pass
