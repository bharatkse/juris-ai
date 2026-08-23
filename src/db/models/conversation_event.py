"""
Conversation event ORM model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import JSON, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import MessageRoleEnum
from src.db.base import Base
from src.db.mixins import PrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from .agent_action import AgentAction
    from .conversation import Conversation
    from .conversation_event import ConversationEvent


class ConversationEvent(
    Base,
    PrimaryKeyMixin,
    TimestampMixin,
):
    """
    Conversation event.

    Represents a single event within a conversation.

    Examples:
        - User message
        - Assistant response
        - System message
        - Tool invocation
        - Tool response

    Events form a tree through ``parent_event_id``, enabling future
    support for agent execution, branching conversations, tool calls,
    and regenerated responses.

    A request can produce at most one event per role. This is enforced
    by the database using ``conversation_id``, ``request_id``, and
    ``role``.
    """

    __tablename__ = "conversation_events"

    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "request_id",
            "role",
            name="uq_conversation_event_request_role",
        ),
    )

    _id_prefix = "evnt"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"),
        nullable=False,
        index=True,
    )

    request_id: Mapped[UUID] = mapped_column(
        nullable=False,
        index=True,
    )

    parent_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversation_events.id"),
        nullable=True,
        index=True,
    )

    role: Mapped[MessageRoleEnum] = mapped_column(
        Enum(
            MessageRoleEnum,
            native_enum=False,
            length=20,
        ),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        String(10_000),
        nullable=False,
    )

    event_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    conversation: Mapped[Conversation] = relationship(
        back_populates="events",
    )

    parent_event: Mapped[ConversationEvent | None] = relationship(
        back_populates="child_events",
        remote_side="ConversationEvent.id",
    )

    child_events: Mapped[list[ConversationEvent]] = relationship(
        back_populates="parent_event",
    )

    agent_actions: Mapped[list[AgentAction]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            "ConversationEvent("
            f"id={self.id!r}, "
            f"request_id={self.request_id!r}, "
            f"role={self.role.value!r}"
            ")"
        )
