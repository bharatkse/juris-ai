"""
Document chunk embedding persistence model.

Stores vector representations of document chunks independently from
the textual chunk itself.

This allows the same chunk to be represented by different embedding
models without coupling DocumentChunk to a specific embedding model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adapters.persistence.sqlalchemy.base import Base
from adapters.persistence.sqlalchemy.mixins import PrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from adapters.persistence.sqlalchemy.models.document_chunk import DocumentChunk


class DocumentChunkEmbedding(
    PrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """
    Vector representation of a document chunk.

    The textual chunk remains independent of the embedding model.
    """

    __tablename__ = "document_chunk_embeddings"

    _id_prefix = "demb"

    chunk_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(
            "document_chunks.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    embedding_model: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    embedding_dimension: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    embedding: Mapped[list[float]] = mapped_column(
        Vector(384),
        nullable=False,
    )

    chunk: Mapped[DocumentChunk] = relationship(
        "DocumentChunk",
        back_populates="embeddings",
    )

    __table_args__ = (
        UniqueConstraint(
            "chunk_id",
            "embedding_model",
            name="uq_document_chunk_embedding_model",
        ),
        Index(
            "document_chunk_embeddings_embedding_idx",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={
                "embedding": "vector_cosine_ops",
            },
        ),
    )
