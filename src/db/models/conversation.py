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
        Mark the conversation as archived.
        """

        self.deleted_at = utcnow()
