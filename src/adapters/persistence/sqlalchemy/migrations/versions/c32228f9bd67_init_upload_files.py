"""
Create library_files table.

Revision ID: c32228f9bd67
Revises: 2ceb9121ef13
Create Date: 2026-08-09 15:01:38.370561
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c32228f9bd67"
down_revision: str | Sequence[str] | None = "2ceb9121ef13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Create the library_files table and its supporting enum types/indexes.

    LibraryFile stores metadata for files uploaded through the application
    upload boundary. It is completely separate from the KnowledgeSource
    and its knowledge chunks/embeddings used by the global RAG corpus.
    """

    storage_type_enum = postgresql.ENUM(
        "LOCAL",
        "S3",
        "AZURE_BLOB",
        "GCS",
        "MINIO",
        name="storage_type",
    )

    library_file_source_enum = postgresql.ENUM(
        # Keep these values synchronized with LibraryFileSourceEnum.
        # Replace/add values if the enum definition contains additional members.
        "USER",
        name="library_file_source",
    )

    library_file_status_enum = postgresql.ENUM(
        "UPLOADED",
        "PROCESSING",
        "READY",
        "FAILED",
        "DELETED",
        name="library_file_status",
    )

    bind = op.get_bind()

    storage_type_enum.create(
        bind,
        checkfirst=True,
    )

    library_file_source_enum.create(
        bind,
        checkfirst=True,
    )

    library_file_status_enum.create(
        bind,
        checkfirst=True,
    )

    op.create_table(
        "library_files",
        sa.Column(
            "conversation_id",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "source_type",
            postgresql.ENUM(
                "USER",
                name="library_file_source",
                create_type=False,
            ),
            nullable=False,
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
                "AZURE_BLOB",
                "GCS",
                "MINIO",
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
                "DELETED",
                name="library_file_status",
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
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_library_files_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_library_files"),
        ),
    )

    op.create_index(
        op.f("ix_library_files_conversation_id"),
        "library_files",
        ["conversation_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_library_files_source_type"),
        "library_files",
        ["source_type"],
        unique=False,
    )

    op.create_index(
        op.f("ix_library_files_checksum"),
        "library_files",
        ["checksum"],
        unique=False,
    )

    op.create_index(
        op.f("ix_library_files_status"),
        "library_files",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    """
    Remove the library_files table and its supporting enum types.
    """

    op.drop_index(
        op.f("ix_library_files_status"),
        table_name="library_files",
    )

    op.drop_index(
        op.f("ix_library_files_checksum"),
        table_name="library_files",
    )

    op.drop_index(
        op.f("ix_library_files_source_type"),
        table_name="library_files",
    )

    op.drop_index(
        op.f("ix_library_files_conversation_id"),
        table_name="library_files",
    )

    op.drop_table("library_files")

    bind = op.get_bind()

    postgresql.ENUM(
        name="library_file_status",
    ).drop(
        bind,
        checkfirst=True,
    )

    postgresql.ENUM(
        name="library_file_source",
    ).drop(
        bind,
        checkfirst=True,
    )

    postgresql.ENUM(
        name="storage_type",
    ).drop(
        bind,
        checkfirst=True,
    )
