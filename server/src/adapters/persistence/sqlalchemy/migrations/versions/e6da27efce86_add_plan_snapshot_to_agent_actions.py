"""add plan_snapshot to agent_actions

Revision ID: e6da27efce86
Revises: c1d8f4a6b023
Create Date: 2026-09-14 11:42:58.476128

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e6da27efce86"
down_revision: str | Sequence[str] | None = "c1d8f4a6b023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "agent_actions",
        sa.Column("plan_snapshot", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("agent_actions", "plan_snapshot")
