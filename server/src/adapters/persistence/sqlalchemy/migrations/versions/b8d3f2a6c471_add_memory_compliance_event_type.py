"""add MEMORY_OPERATION to compliance_event_type

Revision ID: b8d3f2a6c471
Revises: a4c1e7d92b35
Create Date: 2026-09-21

compliance_log.event_type is a native Postgres enum
(compliance_event_type), so recording changes to a user's long-term
memory needs a new label before any code can write one. Labels are the
Python enum member NAMES (see 437f76f8ffb3), hence the upper-case value.

One label only: a native enum value can be added but never removed
(there is no ALTER TYPE ... DROP VALUE), so the specific operation
(stored/updated/deleted/consent_withdrawn/...) lives in the row's JSON
payload, not in more enum labels.

ALTER TYPE ... ADD VALUE runs in an autocommit block: it cannot be
combined with other statements in the migration's transaction, and a
newly added label cannot be used until it commits.

Downgrade is deliberately a no-op, same as b7c4d2e1f809: the label
cannot be dropped, and compliance_log is insert-only, so any rows
already written with it must stay valid. A downgraded database keeps
an extra, unused label rather than exactly reproducing the old type.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8d3f2a6c471"
down_revision: str | Sequence[str] | None = "a4c1e7d92b35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the MEMORY_OPERATION label."""

    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE compliance_event_type ADD VALUE IF NOT EXISTS 'MEMORY_OPERATION'")


def downgrade() -> None:
    """
    No-op: a Postgres enum label cannot be dropped, and compliance_log is
    insert-only, so existing MEMORY_OPERATION rows must remain valid.
    """
