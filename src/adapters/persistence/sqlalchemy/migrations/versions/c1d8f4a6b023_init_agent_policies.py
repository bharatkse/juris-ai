"""init agent policies

Revision ID: c1d8f4a6b023
Revises: b6e2a4c9f018
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d8f4a6b023"
down_revision: str | Sequence[str] | None = "b6e2a4c9f018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "agent_policies",
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("allowed_tools", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_policies")),
    )
    op.create_index(
        op.f("ix_agent_policies_agent_id"),
        "agent_policies",
        ["agent_id"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_agent_policies_agent_id"), table_name="agent_policies")
    op.drop_table("agent_policies")
