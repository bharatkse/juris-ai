"""
Document chunk persistence model.

A DocumentChunk represents extracted textual content belonging to a
source document.

The chunk itself is intentionally independent of any embedding model.
Embeddings are persisted separately so that different embedding models
or embedding dimensions can be introduced without changing the
semantic representation of the chunk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Computed, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adapters.persistence.sqlalchemy.base import Base
from adapters.persistence.sqlalchemy.mixins import PrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from adapters.persistence.sqlalchemy.models.document import Document
    from adapters.persistence.sqlalchemy.models.document_chunk_embedding import (
        DocumentChunkEmbedding,
    )


class DocumentChunk(
    PrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """
    Persisted textual chunk extracted from a source document.

    DocumentChunk contains source/provenance information and textual
    content only. It does not depend on a particular embedding model.
    """

    __tablename__ = "document_chunks"

    _id_prefix = "dchk"

    document_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # NOTE: renamed from `metadata` -> `chunk_metadata`. `metadata` is
    # a reserved attribute name on SQLAlchemy declarative models
    # (Base.metadata is the MetaData registry) — defining a column
    # with that name raises InvalidRequestError at class-definition
    # time, before any query ever runs. This is a hard SQLAlchemy
    # constraint, not a style preference.
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    text_tsv: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', text)",
            persisted=True,
        ),
        nullable=True,
    )

    document: Mapped[Document | None] = relationship(
        "Document",
        back_populates="chunks",
    )

    embeddings: Mapped[list[DocumentChunkEmbedding]] = relationship(
        "DocumentChunkEmbedding",
        back_populates="chunk",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index(
            "document_chunks_tsv_idx",
            "text_tsv",
            postgresql_using="gin",
        ),
    )
