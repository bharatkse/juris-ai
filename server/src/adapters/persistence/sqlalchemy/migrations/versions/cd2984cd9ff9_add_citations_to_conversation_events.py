"""add citations to conversation_events

Revision ID: cd2984cd9ff9
Revises: 8473ede09ced
Create Date: 2026-09-14 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cd2984cd9ff9"
down_revision: str | Sequence[str] | None = "8473ede09ced"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "conversation_events",
        sa.Column("citations", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("conversation_events", "citations")
