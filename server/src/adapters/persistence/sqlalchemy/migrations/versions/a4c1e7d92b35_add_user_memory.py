"""add user memory (Phase 1: user-scoped preference memory)

Revision ID: a4c1e7d92b35
Revises: dd110a14caf1
Create Date: 2026-09-21

Adds durable, per-user memory:

* user_memories -- one short user-stated fact per row, with an embedding
  for similarity retrieval. Scoped to a user; scope_type is CHECK-limited
  to 'user' for now (a 'matter' scope needs a matters model and its own
  migration to widen the constraint).
* users.memory_enabled / memory_consent_updated_at -- opt-in consent
  flag (default false) and when it last changed.
* conversations.memory_disabled / memory_extracted_through_created_at --
  per-conversation "don't remember this" switch and the extraction
  watermark.

kind/status/scope_type are VARCHAR + CHECK rather than native Postgres
enums: an enum can gain a value but never lose one, and scope_type in
particular is expected to widen.

There is deliberately no vector index. Per-user row counts are small
and every query filters on user_id first, so similarity is an exact
scan of the already-filtered rows.

user_memories.content is VARCHAR(300), mirroring
core.constants.USER_MEMORY_MAX_CONTENT_CHARS. The value is frozen here
on purpose: widening the cap later needs a new migration, not an edit
to this one.

No GRANT is issued here, on purpose. The restricted runtime role
(APP_DB_USER) gets DML on new tables through the standing
ALTER DEFAULT PRIVILEGES set up once per database by the role
bootstrap (docker/dependencies/init/postgres/_create_app_role.lib,
run by 01-create-app-role.sh on a fresh volume or by
scripts/bash/setup_app_role.sh on an existing one) -- the same
mechanism every other table relies on, and the documented convention
("Migration conventions" in claude.md). Verified on fresh databases:
with the bootstrap applied first, a table created by this migration is
readable/writable by the app role with no manual grant; without the
bootstrap the app role has no access to ANY table, so a per-table GRANT
here would not make such a database usable. Default privileges are
per-database, which is why a database created outside the bootstrap
needs setup_app_role.sh, not a migration change.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "a4c1e7d92b35"
down_revision: str | Sequence[str] | None = "dd110a14caf1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create user_memories and add the consent/watermark columns."""

    op.create_table(
        "user_memories",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column(
            "scope_type",
            sa.String(length=16),
            server_default="user",
            nullable=False,
        ),
        sa.Column("scope_id", sa.String(length=64), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("content", sa.String(length=300), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding", Vector(dim=384), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("source_conversation_id", sa.String(length=64), nullable=True),
        sa.Column("source_event_id", sa.String(length=64), nullable=True),
        sa.Column(
            "confidence",
            sa.Float(),
            server_default="1.0",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="active",
            nullable=False,
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('preference', 'profile', 'fact')",
            name=op.f("ck_user_memories_kind_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'superseded', 'pending')",
            name=op.f("ck_user_memories_status_valid"),
        ),
        sa.CheckConstraint(
            "scope_type IN ('user')",
            name=op.f("ck_user_memories_scope_type_valid"),
        ),
        sa.CheckConstraint(
            "scope_type <> 'user' OR scope_id IS NULL",
            name=op.f("ck_user_memories_user_scope_has_no_scope_id"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_memories_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_conversation_id"],
            ["conversations.id"],
            name=op.f("fk_user_memories_source_conversation_id_conversations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["source_event_id"],
            ["conversation_events.id"],
            name=op.f("fk_user_memories_source_event_id_conversation_events"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_memories")),
    )

    op.create_index(
        "ix_user_memories_user_id_status",
        "user_memories",
        ["user_id", "status"],
        unique=False,
    )

    op.create_index(
        "uq_user_memories_user_id_content_hash_active",
        "user_memories",
        ["user_id", "content_hash"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.add_column(
        "users",
        sa.Column(
            "memory_enabled",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "memory_consent_updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "conversations",
        sa.Column(
            "memory_disabled",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "conversations",
        sa.Column(
            "memory_extracted_through_created_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """
    Drop user_memories and the consent/watermark columns.

    Destructive by nature: every stored memory, and every user's
    consent record, is discarded.
    """

    op.drop_column("conversations", "memory_extracted_through_created_at")
    op.drop_column("conversations", "memory_disabled")

    op.drop_column("users", "memory_consent_updated_at")
    op.drop_column("users", "memory_enabled")

    op.drop_index(
        "uq_user_memories_user_id_content_hash_active",
        table_name="user_memories",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_index("ix_user_memories_user_id_status", table_name="user_memories")

    op.drop_table("user_memories")
