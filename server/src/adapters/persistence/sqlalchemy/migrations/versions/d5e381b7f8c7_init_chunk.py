"""
Create knowledge_chunks table.

Revision ID: d5e381b7f8c7
Revises: c7a91e4b2d63
Create Date: 2026-08-27 19:03:27.359694
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d5e381b7f8c7"
down_revision: str | Sequence[str] | None = "c7a91e4b2d63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Create the knowledge_chunks table.

    KnowledgeChunk stores the textual representation of a
    KnowledgeSource. Embedding representations are intentionally
    persisted separately in the knowledge_embeddings table.
    """

    op.create_table(
        "knowledge_chunks",
        sa.Column(
            "knowledge_source_id",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "text",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "chunk_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "text_tsv",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', text)",
                persisted=True,
            ),
            nullable=True,
        ),
        sa.Column(
            "id",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_source_id"],
            ["knowledge_sources.id"],
            name=op.f(
                "fk_knowledge_chunks_knowledge_source_id_knowledge_sources",
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_knowledge_chunks"),
        ),
    )

    op.create_index(
        op.f("ix_knowledge_chunks_knowledge_source_id"),
        "knowledge_chunks",
        ["knowledge_source_id"],
        unique=False,
    )

    op.create_index(
        "knowledge_chunks_tsv_idx",
        "knowledge_chunks",
        ["text_tsv"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    """
    Drop the knowledge_chunks table and its indexes.
    """

    op.drop_index(
        "knowledge_chunks_tsv_idx",
        table_name="knowledge_chunks",
        postgresql_using="gin",
    )

    op.drop_index(
        op.f("ix_knowledge_chunks_knowledge_source_id"),
        table_name="knowledge_chunks",
    )

    op.drop_table(
        "knowledge_chunks",
    )
