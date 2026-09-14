"""fix naive timestamp columns on approvals and agent_actions

Revision ID: 8473ede09ced
Revises: e6da27efce86
Create Date: 2026-09-14 11:53:35.582264

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8473ede09ced"
down_revision: str | Sequence[str] | None = "e6da27efce86"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    approvals.expires_at/decided_at and agent_actions.executed_at were
    declared as bare `Mapped[datetime]`, which SQLAlchemy maps to a
    naive TIMESTAMP WITHOUT TIME ZONE column -- every real datetime
    this codebase constructs is timezone-aware (datetime.now(UTC)),
    which asyncpg rejects outright against a naive column. These
    tables had zero real rows before today (the HITL approval flow
    they belong to was unreachable), so a plain ALTER ... USING cast
    is safe -- there is no historical naive data whose true offset
    would need to be guessed.
    """
    op.alter_column(
        "approvals",
        "expires_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(timezone=False),
        postgresql_using="expires_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "approvals",
        "decided_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(timezone=False),
        postgresql_using="decided_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "agent_actions",
        "executed_at",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(timezone=False),
        postgresql_using="executed_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "approvals",
        "expires_at",
        type_=sa.DateTime(timezone=False),
        existing_type=sa.DateTime(timezone=True),
    )
    op.alter_column(
        "approvals",
        "decided_at",
        type_=sa.DateTime(timezone=False),
        existing_type=sa.DateTime(timezone=True),
    )
    op.alter_column(
        "agent_actions",
        "executed_at",
        type_=sa.DateTime(timezone=False),
        existing_type=sa.DateTime(timezone=True),
    )
