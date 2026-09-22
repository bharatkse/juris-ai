"""
User memory persistence model.

A UserMemory is one short, durable, user-stated fact (a working
preference or profile detail) that persists across conversations for a
single user. It is deliberately not a transcript and not part of the
global knowledge/RAG corpus: KnowledgeSource/KnowledgeChunk are shared
by every user and the RAG retriever has no per-user filter, so user data
must never be stored there.

Isolation is by user_id. Every access goes through UserMemoryRepository,
whose methods all require a keyword-only user_id.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from adapters.persistence.sqlalchemy.base import Base
from adapters.persistence.sqlalchemy.mixins import PrimaryKeyMixin, TimestampMixin
from core.constants import USER_MEMORY_MAX_CONTENT_CHARS
from core.enums import (
    UserMemoryKindEnum,
    UserMemoryScopeEnum,
    UserMemoryStatusEnum,
)
from core.utils.datetime import utcnow


def _in_list(column: str, enum_type: type[StrEnum]) -> str:
    values = ", ".join(f"'{member.value}'" for member in enum_type)

    return f"{column} IN ({values})"


class UserMemory(
    PrimaryKeyMixin,
    TimestampMixin,
    Base,
):
    """
    One durable fact about a user, retrievable by semantic similarity.

    kind / status / scope_type are plain strings guarded by CHECK
    constraints rather than native Postgres enums: a native enum can
    gain a value but never lose one (ALTER TYPE has no DROP VALUE), and
    scope_type in particular is expected to widen to "matter" later --
    a CHECK constraint changes with one migration statement.
    """

    __tablename__ = "user_memories"

    _id_prefix = "umem"

    user_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    # Phase 1 is user-scoped only. scope_id is reserved for a future
    # matter identifier and must be NULL while scope_type is "user"
    # (enforced by ck_user_memories_user_scope_has_no_scope_id).
    scope_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=UserMemoryScopeEnum.USER.value,
        server_default=UserMemoryScopeEnum.USER.value,
    )

    scope_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    kind: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        String(USER_MEMORY_MAX_CONTENT_CHARS),
        nullable=False,
    )

    # sha256 of the normalized content -- dedupe key, never the content.
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    # Same model and dimension as KnowledgeEmbedding, so one embedding
    # provider serves both. embedding_model is stored because vectors
    # from different models are not comparable.
    embedding: Mapped[list[float]] = mapped_column(
        Vector(384),
        nullable=False,
    )

    embedding_model: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # Provenance only. SET NULL: deleting a conversation must not
    # cascade into the user's memories.
    source_conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "conversations.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    source_event_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "conversation_events.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        server_default="1.0",
    )

    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=UserMemoryStatusEnum.ACTIVE.value,
        server_default=UserMemoryStatusEnum.ACTIVE.value,
    )

    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    # Sliding window: last_used_at + USER_MEMORY_RETENTION_DAYS. NULL
    # means "never expires" and is never written by the service; a row
    # past expires_at is treated as inactive at query time.
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        # Every query filters on user_id first, then status. No HNSW
        # index: per-user row counts are small (see
        # USER_MEMORY_MAX_PER_USER), so similarity is an exact scan of
        # the already-filtered rows.
        Index(
            "ix_user_memories_user_id_status",
            "user_id",
            "status",
        ),
        # At most one ACTIVE row per (user, content). Superseded and
        # pending rows may repeat a hash.
        Index(
            "uq_user_memories_user_id_content_hash_active",
            "user_id",
            "content_hash",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
        CheckConstraint(
            _in_list("kind", UserMemoryKindEnum),
            name="kind_valid",
        ),
        CheckConstraint(
            _in_list("status", UserMemoryStatusEnum),
            name="status_valid",
        ),
        CheckConstraint(
            _in_list("scope_type", UserMemoryScopeEnum),
            name="scope_type_valid",
        ),
        CheckConstraint(
            "scope_type <> 'user' OR scope_id IS NULL",
            name="user_scope_has_no_scope_id",
        ),
    )

    def __repr__(self) -> str:
        # Never include content: it is user data.
        return f"UserMemory(id={self.id!r}, kind={self.kind!r}, status={self.status!r})"
