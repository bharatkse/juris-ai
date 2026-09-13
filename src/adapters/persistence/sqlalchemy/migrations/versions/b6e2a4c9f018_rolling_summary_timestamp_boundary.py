"""rolling summary timestamp boundary (drop circular FK)

Revision ID: b6e2a4c9f018
Revises: f2b43ec1b2ec
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6e2a4c9f018"
down_revision: str | Sequence[str] | None = "f2b43ec1b2ec"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(
        "fk_conversations_rolling_summary_through_event_id_conve_4c61",
        "conversations",
        type_="foreignkey",
    )
    op.drop_column("conversations", "rolling_summary_through_event_id")
    op.add_column(
        "conversations",
        sa.Column("rolling_summary_through_created_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("conversations", "rolling_summary_through_created_at")
    op.add_column(
        "conversations",
        sa.Column("rolling_summary_through_event_id", sa.String(length=64), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversations_rolling_summary_through_event_id_conve_4c61",
        "conversations",
        "conversation_events",
        ["rolling_summary_through_event_id"],
        ["id"],
    )
