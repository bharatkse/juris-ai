"""add conversation rolling summary

Revision ID: a92c7e1f5d34
Revises: f3d8a91c4b27
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a92c7e1f5d34"
down_revision: str | Sequence[str] | None = "f3d8a91c4b27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "conversations",
        sa.Column("rolling_summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column("rolling_summary_through_event_id", sa.String(length=64), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_conversations_rolling_summary_through_event_id_conversation_events"),
        "conversations",
        "conversation_events",
        ["rolling_summary_through_event_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("fk_conversations_rolling_summary_through_event_id_conversation_events"),
        "conversations",
        type_="foreignkey",
    )
    op.drop_column("conversations", "rolling_summary_through_event_id")
    op.drop_column("conversations", "rolling_summary")
