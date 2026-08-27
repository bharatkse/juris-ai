from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adapters.persistence.sqlalchemy.base import Base
from adapters.persistence.sqlalchemy.mixins import PrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from adapters.persistence.sqlalchemy.models.document import Document


class DocumentChunk(
    PrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    __tablename__ = "document_chunks"
    _id_prefix = "dchk"

    document_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        nullable=False,
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

    embedding_model: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(384),
        nullable=True,
    )

    text_tsv: Mapped[Any] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', text)",
            persisted=True,
        ),
        nullable=True,
    )

    document: Mapped["Document"] = relationship(
        "Document",
        back_populates="chunks",
    )

    __table_args__ = (
        Index(
            "document_chunks_embedding_idx",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={
                "embedding": "vector_cosine_ops",
            },
        ),
        Index(
            "document_chunks_tsv_idx",
            "text_tsv",
            postgresql_using="gin",
        ),
    )
