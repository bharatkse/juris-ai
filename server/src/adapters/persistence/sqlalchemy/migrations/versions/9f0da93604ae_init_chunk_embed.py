"""Create knowledge embeddings.

Revision ID: 9f0da93604ae
Revises: d5e381b7f8c7
Create Date: 2026-09-01 01:36:33.777786
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "9f0da93604ae"
down_revision: str | Sequence[str] | None = "d5e381b7f8c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create knowledge_embeddings table."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_embeddings",
        sa.Column(
            "chunk_id",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "embedding_model",
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            "embedding_dimension",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "embedding",
            Vector(dim=384),
            nullable=False,
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
            ["chunk_id"],
            ["knowledge_chunks.id"],
            name=op.f("fk_knowledge_embeddings_chunk_id_knowledge_chunks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_knowledge_embeddings"),
        ),
        sa.UniqueConstraint(
            "chunk_id",
            "embedding_model",
            name="uq_knowledge_chunk_embedding_model",
        ),
    )

    op.create_index(
        "knowledge_chunk_embeddings_embedding_idx",
        "knowledge_embeddings",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={
            "embedding": "vector_cosine_ops",
        },
    )

    op.create_index(
        op.f("ix_knowledge_embeddings_chunk_id"),
        "knowledge_embeddings",
        ["chunk_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_knowledge_embeddings_embedding_model"),
        "knowledge_embeddings",
        ["embedding_model"],
        unique=False,
    )


def downgrade() -> None:
    """Drop knowledge_embeddings table and indexes."""

    op.drop_index(
        op.f("ix_knowledge_embeddings_embedding_model"),
        table_name="knowledge_embeddings",
    )

    op.drop_index(
        op.f("ix_knowledge_embeddings_chunk_id"),
        table_name="knowledge_embeddings",
    )

    op.drop_index(
        "knowledge_chunk_embeddings_embedding_idx",
        table_name="knowledge_embeddings",
        postgresql_using="hnsw",
        postgresql_ops={
            "embedding": "vector_cosine_ops",
        },
    )

    op.drop_table("knowledge_embeddings")
