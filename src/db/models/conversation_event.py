"""
Conversation event ORM model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import MessageRole
from src.db.base import Base
from src.db.mixins import PrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
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

    Events form a tree through `parent_event_id`, enabling future
    support for agent execution, branching conversations, tool calls,
    and regenerated responses.
    """

    __tablename__ = "conversation_events"

    _id_prefix = "event"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id"),
        nullable=False,
        index=True,
    )

    parent_event_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversation_events.id"),
        nullable=True,
        index=True,
    )

    role: Mapped[MessageRole] = mapped_column(
        String(20),
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

    def __repr__(self) -> str:
        return f"ConversationEvent(" f"id={self.id!r}, " f"role={self.role.value!r}" f")"
