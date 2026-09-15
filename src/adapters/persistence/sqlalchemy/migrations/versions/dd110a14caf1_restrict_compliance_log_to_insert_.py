"""restrict compliance_log to insert/select for the real restricted
app role (APP_DB_USER / juris_ai_app)

Revision ID: dd110a14caf1
Revises: 48e4b24358b7
Create Date: 2026-09-15 12:40:27.673141

Corrects migration 9338dbb3a96f, which this branch also introduces:
that migration REVOKEs UPDATE/DELETE from `_app_role()` ==
config.database.DatabaseSettings.DB_USER -- the schema-owning
admin/migration role, confirmed there (and in this migration's own
history) to be both compliance_log's owner and a Postgres superuser,
for which REVOKE has no effect at all (PostgreSQL never applies ACL
checks to a table's owner or to a superuser). It was written before
a real, properly-scoped runtime role existed in this project, so it
had nothing else to target -- see that migration's docstring, which
states this limitation explicitly rather than hiding it.

APP_DB_USER (juris_ai_app in local dev -- see deploy/docker/init/
postgres/01-create-app-role.sh) now exists: a NOSUPERUSER role that
does not own compliance_log, granted baseline SELECT/INSERT/UPDATE/
DELETE only via ALTER DEFAULT PRIVILEGES, not ownership. REVOKE
against *this* role is real, load-bearing restriction -- unlike
9338dbb3a96f's REVOKE, which remains in place (harmless, and still
correct as a statement of intent against DB_USER) but was never
capable of restricting anything on its own. The actual
belt-and-suspenders guarantee for compliance_log is: this REVOKE
blocks juris_ai_app at the grant level (verified in
tests/e2e/test_compliance_log_immutability.py -- the
grant-vs-trigger isolation test), and the BEFORE UPDATE OR DELETE
trigger from 48e4b24358b7 blocks the admin/owner/superuser role
regardless of any REVOKE, since triggers apply unconditionally to
every role.

Like 9338dbb3a96f, this is a no-op (upgrade()/downgrade() return
immediately) when APP_DB_USER isn't configured -- e.g. any
environment that doesn't use this local-dev role split at all;
cloud/RDS role separation is explicitly out of scope for this
project as of this migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dd110a14caf1"
down_revision: str | Sequence[str] | None = "48e4b24358b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _app_role() -> str | None:
    """
    The restricted runtime role -- distinct from 9338dbb3a96f's
    _app_role(), which (by necessity, at the time it was written)
    resolved to DB_USER, the admin/migration role. This one resolves
    to APP_DB_USER, the actual role session.py's shared engine
    connects as for normal request handling.

    Returns None (upgrade()/downgrade() then no-op, not error) when
    APP_DB_USER isn't configured -- environments that don't use this
    local-dev role split at all must not have this migration break
    them.
    """

    from config.settings import get_settings

    return get_settings().database.APP_DB_USER


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
