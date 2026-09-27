"""Create knowledge sources.

Revision ID: c7a91e4b2d63
Revises: 8f3a1c2e7b91
Create Date: 2026-09-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c7a91e4b2d63"
down_revision: str | Sequence[str] | None = "8f3a1c2e7b91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create knowledge_sources table."""

    knowledge_source_enum = postgresql.ENUM(
        "DOCUMENT",
        "URL",
        "WEB",
        name="knowledge_source",
    )

    storage_type_enum = postgresql.ENUM(
        "LOCAL",
        "S3",
        name="storage_type",
    )

    knowledge_status_enum = postgresql.ENUM(
        "UPLOADED",
        "PROCESSING",
        "READY",
        "FAILED",
        name="knowledge_status",
    )

    knowledge_source_enum.create(op.get_bind(), checkfirst=True)
    storage_type_enum.create(op.get_bind(), checkfirst=True)
    knowledge_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "knowledge_sources",
        sa.Column(
            "source_type",
            postgresql.ENUM(
                "DOCUMENT",
                "URL",
                "WEB",
                name="knowledge_source",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "source_url",
            sa.String(length=2048),
            nullable=True,
        ),
        sa.Column(
            "original_filename",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "filename",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "mime_type",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            "size",
            sa.Integer(),
            nullable=True,
        ),
        sa.Column(
            "storage_type",
            postgresql.ENUM(
                "LOCAL",
                "S3",
                name="storage_type",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "storage_path",
            sa.String(length=1024),
            nullable=True,
        ),
        sa.Column(
            "checksum",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "UPLOADED",
                "PROCESSING",
                "READY",
                "FAILED",
                name="knowledge_status",
                create_type=False,
            ),
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
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_knowledge_sources"),
        ),
    )

    op.create_index(
        op.f("ix_knowledge_sources_source_type"),
        "knowledge_sources",
        ["source_type"],
        unique=False,
    )

    op.create_index(
        op.f("ix_knowledge_sources_checksum"),
        "knowledge_sources",
        ["checksum"],
        unique=False,
    )

    op.create_index(
        op.f("ix_knowledge_sources_status"),
        "knowledge_sources",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """Drop knowledge_sources table and enums."""

    op.drop_index(
        op.f("ix_knowledge_sources_status"),
        table_name="knowledge_sources",
    )

    op.drop_index(
        op.f("ix_knowledge_sources_checksum"),
        table_name="knowledge_sources",
    )

    op.drop_index(
        op.f("ix_knowledge_sources_source_type"),
        table_name="knowledge_sources",
    )

    op.drop_table("knowledge_sources")

    bind = op.get_bind()

    postgresql.ENUM(
        name="knowledge_status",
    ).drop(bind, checkfirst=True)

    postgresql.ENUM(
        name="storage_type",
    ).drop(bind, checkfirst=True)

    postgresql.ENUM(
        name="knowledge_source",
    ).drop(bind, checkfirst=True)
