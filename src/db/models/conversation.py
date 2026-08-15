"""
Conversation ORM model.
"""

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.constants import DEFAULT_CONVERSATION_TITLE
from src.core.datetime import utcnow
from src.db.base import Base
from src.db.mixins import PrimaryKeyMixin, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from .conversation_event import ConversationEvent
    from .document import Document
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

    documents: Mapped[list["Document"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
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
