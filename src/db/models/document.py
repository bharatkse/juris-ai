"""
Document model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import DocumentStatusEnum, StorageTypeEnum
from src.db.base import Base
from src.db.mixins import PrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from src.db.models.conversation import Conversation


class Document(
    PrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """
    Uploaded document metadata.
    """

    __tablename__ = "documents"

    _id_prefix = "doc"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey(
            "conversations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Generated filename used by the storage provider.
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    storage_type: Mapped[StorageTypeEnum] = mapped_column(
        Enum(
            StorageTypeEnum,
            name="storage_type",
        ),
        nullable=False,
        default=StorageTypeEnum.LOCAL,
    )

    # Provider-specific object location.
    storage_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )

    # SHA-256 checksum for integrity verification.
    checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    status: Mapped[DocumentStatusEnum] = mapped_column(
        Enum(
            DocumentStatusEnum,
            name="document_status",
        ),
        nullable=False,
        default=DocumentStatusEnum.UPLOADED,
        index=True,
    )

    conversation: Mapped[Conversation] = relationship(
        back_populates="documents",
    )
