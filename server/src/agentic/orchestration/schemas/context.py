"""
Immutable context models used during orchestration.

The orchestration context is built once and remains immutable
throughout planning and execution.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from core.dto.tool import ToolFileDTO
from core.dto.user_memory import UserMemoryContextItem
from core.models.conversation import ConversationMessageSchema
from core.types import ConversationId, UserId


class RequestContext(BaseModel):
    """
    Request-scoped information.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    message: str


class ConversationContext(BaseModel):
    """
    Conversation context available during planning.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    conversation_id: ConversationId

    history: list[ConversationMessageSchema] = Field(
        default_factory=list,
    )

    summary: str | None = None

    user_memory: tuple[UserMemoryContextItem, ...] = ()


class UserContext(BaseModel):
    """
    User information available during planning.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    user_id: UserId


class DocumentContext(BaseModel):
    """
    Attachments available during planning.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    attachments: tuple[ToolFileDTO, ...] = ()


class RuntimeContext(BaseModel):
    """
    Runtime execution information.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )

    preferred_model: str | None = None

    max_parallelism: int = 4


class OrchestrationContext(BaseModel):
    """
    Immutable context consumed by the execution planner.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    request: RequestContext

    conversation: ConversationContext

    user: UserContext

    documents: DocumentContext = Field(
        default_factory=DocumentContext,
    )

    runtime: RuntimeContext = Field(
        default_factory=RuntimeContext,
    )
