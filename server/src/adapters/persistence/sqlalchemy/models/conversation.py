"""
Conversation ORM model.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adapters.persistence.sqlalchemy.base import Base
from adapters.persistence.sqlalchemy.mixins import (
    PrimaryKeyMixin,
    SoftDeleteMixin,
    TimestampMixin,
)
from adapters.persistence.sqlalchemy.models.library import Library
from core.constants import DEFAULT_CONVERSATION_TITLE
from core.utils.datetime import utcnow

if TYPE_CHECKING:
    from .conversation_event import ConversationEvent
    from .user import User


class Conversation(
    Base,
    PrimaryKeyMixin,
    TimestampMixin,
    SoftDeleteMixin,
):
    """
    Conversation table.
    """

    __tablename__ = "conversations"
    _id_prefix = "conv"

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default=lambda: DEFAULT_CONVERSATION_TITLE,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    user: Mapped["User"] = relationship(
        back_populates="conversations",
    )

    events: Mapped[list["ConversationEvent"]] = relationship(
        back_populates="conversation",
        order_by="ConversationEvent.created_at",
    )

    library: Mapped[list["Library"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    # Within-conversation compression (not cross-conversation memory:
    # this summary is only ever read back into this same conversation's
    # own history): a compact summary of events created at or
    # before rolling_summary_through_created_at, folded in by
    # ConversationSummarizationService once the unsummarized tail grows
    # past UNSUMMARIZED_EVENT_LIMIT. NULL until a conversation is long
    # enough to need it. Prepended to history in place of the raw
    # discarded events it replaces -- see application/services/
    # conversation_summarization.py.
    #
    # A plain timestamp, not a FK to conversation_events.id: the
    # summarization boundary only needs "events up to this point in
    # time", not a hard reference to one specific event row. An FK here
    # previously created a real circular dependency between
    # conversations and conversation_events (each referencing the
    # other), which confused SQLAlchemy's table-sort logic (surfaced as
    # a real SAWarning in the test fixture, not just a theoretical
    # concern) despite being harmless in practice. A timestamp carries
    # everything ensure_summarized() actually needs and breaks the
    # cycle.
    rolling_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    rolling_summary_through_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Per-conversation "don't remember this" switch. When True, nothing
    # from this conversation is ever extracted into UserMemory,
    # regardless of the user's account-level consent. It stops future
    # extraction only; it does not delete facts already stored.
    memory_disabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )

    # Extraction watermark, same idiom as rolling_summary_through_created_at:
    # a plain timestamp (not an FK to conversation_events) meaning "USER
    # events created at or before this instant have already been considered
    # for memory extraction". NULL until the first extraction pass.
    memory_extracted_through_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return f"Conversation(" f"id={self.id!r}, " f"title={self.title!r}" f")"

    @property
    def is_active(self) -> bool:
        """
        Return True when conversation is not deleted.
        """
        return self.deleted_at is None

    def archive(self) -> None:
        """
        Archive the conversation.

        The operation is idempotent: once archived, the original
        deletion timestamp is preserved.
        """

        if self.deleted_at is None:
            self.deleted_at = utcnow()
