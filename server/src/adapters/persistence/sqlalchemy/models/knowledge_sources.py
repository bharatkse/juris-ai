from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adapters.persistence.sqlalchemy.base import Base
from adapters.persistence.sqlalchemy.mixins import PrimaryKeyMixin, TimestampMixin
from core.enums import (
    KnowledgeSourceEnum,
    KnowledgeStatusEnum,
    StorageTypeEnum,
)

if TYPE_CHECKING:
    from adapters.persistence.sqlalchemy.models.knowledge_chunk import KnowledgeChunk


class KnowledgeSource(
    PrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """
    Persisted metadata for an approved knowledge source.

    KnowledgeSource represents material that is eligible for the
    global knowledge/RAG corpus.

    It is independent of user-uploaded files.
    """

    __tablename__ = "knowledge_sources"

    _id_prefix = "ksrc"

    source_type: Mapped[KnowledgeSourceEnum] = mapped_column(
        Enum(
            KnowledgeSourceEnum,
            name="knowledge_source",
        ),
        nullable=False,
        index=True,
    )

    source_url: Mapped[str | None] = mapped_column(
        String(2048),
        nullable=True,
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

    status: Mapped[KnowledgeStatusEnum] = mapped_column(
        Enum(
            KnowledgeStatusEnum,
            name="knowledge_status",
        ),
        nullable=False,
        default=KnowledgeStatusEnum.UPLOADED,
        index=True,
    )

    chunks: Mapped[list[KnowledgeChunk]] = relationship(
        "KnowledgeChunk",
        back_populates="knowledge_source",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
