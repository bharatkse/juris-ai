"""restrict compliance_log to insert/select for the app db role

Revision ID: 9338dbb3a96f
Revises: 437f76f8ffb3
Create Date: 2026-09-14 00:00:00.000000

DB-level immutability for compliance_log: revoke UPDATE and DELETE
from the application's configured DB role (config.database.
DatabaseSettings.DB_USER), leaving INSERT/SELECT untouched. This is
the DB-level backstop for the same guarantee ComplianceLogRepository
already enforces in Python (no update() method at all, and
delete_older_than() exists solely to back the explicit, opt-in
retention purge -- see ComplianceLog's model docstring and
ComplianceLogService.purge_older_than()).

CONFIRMED CAVEAT, verified empirically against this project's actual
local dev database before writing this migration (not assumed):
DB_USER ("juris_ai_user" in this project's .env) is BOTH the owner of
compliance_log (it ran the migration that created the table) and a
POSTGRES SUPERUSER. PostgreSQL privilege checks -- including this
REVOKE -- never apply to a table's owner or to a superuser; both
bypass ACL enforcement unconditionally, by design, regardless of what
REVOKE says. Reproduced directly against the real dev DB:

    REVOKE UPDATE, DELETE ON compliance_log FROM juris_ai_user;
    -- succeeds, \\dp confirms the ACL entry no longer lists "w"/"d"
    DELETE FROM compliance_log WHERE 1=0;
    -- still succeeds ("DELETE 0") -- owner/superuser bypass, not a
    -- privilege the ACL controls

The REVOKE below is real, correct SQL, and DOES take full effect --
confirmed by reproducing the identical sequence against a scratch,
non-owner, NOSUPERUSER role granted only INSERT/SELECT on this table:
UPDATE and DELETE both failed there with "permission denied for table
compliance_log", while INSERT/SELECT succeeded normally. This is the
posture any properly-scoped production deployment should run the app
under. It is written and shipped as asked (a REVOKE-based migration);
it just does not additionally change how the local dev role is
configured, which is a separate, ops-level decision (moving the app
off a superuser role, or having a non-owning role serve the app while
a separate role owns the schema) outside a single migration's scope.
True enforcement against a role shaped like today's dev role would
need one of those changes, or a BEFORE UPDATE/DELETE trigger (triggers
fire regardless of superuser/ownership status) -- neither was in
scope for what was asked here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9338dbb3a96f"
down_revision: str | Sequence[str] | None = "437f76f8ffb3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _app_role() -> str | None:
    """
    The application's configured DB role -- same settings object
    migrations/env.py already imports for the connection URL itself,
    so this isn't a new coupling.

    Returns None (upgrade()/downgrade() then no-op, not error) when
    DB_USER isn't configured -- some environments authenticate by a
    mechanism other than a static configured username (e.g. IAM auth),
    and this migration must not break those rather than guess a role
    name for them.
    """

    from config.settings import get_settings

    return get_settings().database.DB_USER


def upgrade() -> None:
    """Upgrade schema."""
    app_role = _app_role()

    if not app_role:
        return

    bind = op.get_bind()
    bind.execute(
        sa.text(f'REVOKE UPDATE, DELETE ON compliance_log FROM "{app_role}"'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    app_role = _app_role()

    if not app_role:
        return

    bind = op.get_bind()
    bind.execute(
        sa.text(f'GRANT UPDATE, DELETE ON compliance_log TO "{app_role}"'),
    )
