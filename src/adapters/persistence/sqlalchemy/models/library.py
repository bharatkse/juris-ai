from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adapters.persistence.sqlalchemy.base import Base
from adapters.persistence.sqlalchemy.mixins import PrimaryKeyMixin, TimestampMixin
from core.enums import (
    LibrarySourceEnum,
    LibraryStatusEnum,
    StorageTypeEnum,
)

if TYPE_CHECKING:
    from adapters.persistence.sqlalchemy.models.conversation import Conversation


class Library(
    PrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """
    Persisted metadata for a user/API-uploaded file.

    Library represents only files supplied to the application
    through an upload boundary.

    It is not a knowledge source and is never persisted as part
    of the global knowledge/RAG corpus.
    """

    __tablename__ = "library"

    _id_prefix = "liby"

    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "conversations.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    source_type: Mapped[LibrarySourceEnum] = mapped_column(
        Enum(
            LibrarySourceEnum,
            name="library_source",
        ),
        nullable=False,
        index=True,
    )

    original_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    size: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    storage_type: Mapped[StorageTypeEnum | None] = mapped_column(
        Enum(
            StorageTypeEnum,
            name="storage_type",
        ),
        nullable=True,
    )

    storage_path: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )

    checksum: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    status: Mapped[LibraryStatusEnum] = mapped_column(
        Enum(
            LibraryStatusEnum,
            name="library_status",
        ),
        nullable=False,
        default=LibraryStatusEnum.UPLOADED,
        index=True,
    )

    conversation: Mapped[Conversation | None] = relationship(
        back_populates="library",
    )
