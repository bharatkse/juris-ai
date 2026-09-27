"""init usage records

Revision ID: f3d8a91c4b27
Revises: b7c4d2e1f809
Create Date: 2026-09-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3d8a91c4b27"
down_revision: str | Sequence[str] | None = "b7c4d2e1f809"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "usage_records",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("period", sa.String(length=10), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_usage_records_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_records")),
        sa.UniqueConstraint(
            "user_id",
            "period",
            "window_start",
            name="uq_usage_records_user_id_period_window_start",
        ),
    )
    op.create_index(
        op.f("ix_usage_records_user_id"),
        "usage_records",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_usage_records_user_id"), table_name="usage_records")
    op.drop_table("usage_records")
