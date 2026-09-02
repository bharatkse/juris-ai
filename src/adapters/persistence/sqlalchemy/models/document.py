"""
Document persistence model.

A Document represents a source artifact available to the application.

Documents may originate from:

    - API-provided files
    - directly ingested files
    - websites

A document may optionally be associated with a conversation.

The model contains source, storage, and lifecycle metadata only.

RAG processing is intentionally not implemented here. A document may
be processed by an ingestion/indexing workflow, but the RAG pipeline
itself operates on generic text and retrieval sources.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adapters.persistence.sqlalchemy.base import Base
from adapters.persistence.sqlalchemy.mixins import PrimaryKeyMixin, TimestampMixin
from core.enums import (
    DocumentSourceEnum,
    DocumentStatusEnum,
    StorageTypeEnum,
)

if TYPE_CHECKING:
    from adapters.persistence.sqlalchemy.models.conversation import Conversation
    from adapters.persistence.sqlalchemy.models.document_chunk import DocumentChunk


class Document(
    PrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """
    Persisted metadata for a source document.

    A document can exist independently or be associated with a
    conversation.

    Source metadata describes where the document originated.
    Storage metadata is present only when the source has a physical
    stored file.

    RAG processing is handled by the ingestion/indexing workflow.
    """

    __tablename__ = "documents"

    _id_prefix = "doct"

    # Optional conversation association.
    #
    # Documents created from a conversation can reference it.
    # Documents created through batch, script, or website ingestion
    # may exist without a conversation.
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "conversations.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    # Origin of the document.
    source_type: Mapped[DocumentSourceEnum] = mapped_column(
        Enum(
            DocumentSourceEnum,
            name="document_source",
        ),
        nullable=False,
        index=True,
    )

    # Original URL for website-originated documents.
    #
    # NULL for file-based sources.
    source_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
    )

    # Original name of the source artifact when available.
    #
    # For a website source this may be NULL because there may be no
    # uploaded file or filename.
    original_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Generated filename used by the storage provider.
    #
    # NULL when the source does not have a physical stored file,
    # such as a website source.
    filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # MIME type of the stored source artifact when applicable.
    #
    # NULL for sources that do not represent a stored file.
    mime_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Size of the stored source artifact in bytes when applicable.
    size: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    # Storage provider used for the physical source artifact.
    #
    # NULL when there is no stored file, such as a website source.
    storage_type: Mapped[StorageTypeEnum | None] = mapped_column(
        Enum(
            StorageTypeEnum,
            name="storage_type",
        ),
        nullable=True,
    )

    # Provider-specific object location.
    #
    # NULL when the source does not have a physical stored file.
    storage_path: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
    )

    # SHA-256 checksum of the source content when available.
    checksum: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
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

    conversation: Mapped[Conversation | None] = relationship(
        back_populates="documents",
    )

    chunks: Mapped[list[DocumentChunk]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
