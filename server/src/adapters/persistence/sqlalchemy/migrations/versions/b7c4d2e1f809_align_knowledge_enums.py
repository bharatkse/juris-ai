"""Align knowledge enum values with the ORM definitions.

Revision ID: b7c4d2e1f809
Revises: 9f0da93604ae
Create Date: 2026-09-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b7c4d2e1f809"
down_revision: str | Sequence[str] | None = "9f0da93604ae"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Align deployed knowledge enum values with the ORM enums."""

    op.execute("ALTER TYPE knowledge_source RENAME VALUE 'DOCUMENT' TO 'FILE'")
    op.execute("ALTER TYPE knowledge_source RENAME VALUE 'URL' TO 'WEBSITE'")
    op.execute("ALTER TYPE knowledge_source RENAME VALUE 'WEB' TO 'TEXT'")
    op.execute("ALTER TYPE knowledge_source ADD VALUE IF NOT EXISTS 'CLOUD_STORAGE'")


def downgrade() -> None:
    """Restore the previous knowledge enum values."""

    # CLOUD_STORAGE cannot be dropped from a Postgres enum type (no
    # ALTER TYPE ... DROP VALUE) -- downgrading only reverts the three
    # renames, so a downgraded DB still has CLOUD_STORAGE as an extra,
    # unused label rather than exactly reproducing the pre-upgrade type.
    op.execute("ALTER TYPE knowledge_source RENAME VALUE 'TEXT' TO 'WEB'")
    op.execute("ALTER TYPE knowledge_source RENAME VALUE 'WEBSITE' TO 'URL'")
    op.execute("ALTER TYPE knowledge_source RENAME VALUE 'FILE' TO 'DOCUMENT'")
