"""add compliance_log immutability trigger

Revision ID: 48e4b24358b7
Revises: 9338dbb3a96f
Create Date: 2026-09-14 00:00:00.000000

BEFORE UPDATE OR DELETE trigger on compliance_log that unconditionally
RAISE EXCEPTIONs -- the real, structural backstop the previous
migration (9338dbb3a96f) could not provide: REVOKE-based privilege
restriction is confirmed (see that migration's docstring) to have NO
effect on a table's owner or on a superuser, and this project's
current app role is both. A trigger has no such exception -- it fires
for every role, owner and superuser included, unconditionally, every
time. Verified live against the real dev DB before writing this
migration (not assumed): with this trigger installed, the app's own
configured role (owner + superuser) gets a hard "permission denied"-
style failure attempting either UPDATE or DELETE on compliance_log.

This makes any real deletion -- specifically the already-built
retention purge (ComplianceLogService.purge_older_than(), invoked only
via scripts/python/purge_compliance_log.py) -- impossible by accident.
The purge script now explicitly disables this trigger immediately
before its one intentional DELETE and re-enables it immediately after,
via ComplianceLogRepository.disable_immutability_guard()/
enable_immutability_guard() -- see that script and repository for the
exact sequence, and tests/e2e/test_compliance_log_immutability.py for
a live proof of both halves (blocked without the explicit disable,
succeeds with it).

Caveat, stated rather than hidden: ALTER TABLE ... DISABLE TRIGGER is
NOT connection/session-scoped -- it is a catalog-level change visible
to every connection against this database until the trigger is
re-enabled. The purge script's disable window is therefore a real,
if brief (one DELETE statement), moment where any other connection
could also bypass the guard. This is the standard, accepted trade-off
for a trigger-based guard that needs a deliberate escape hatch, not
something this migration works around.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "48e4b24358b7"
down_revision: str | Sequence[str] | None = "9338dbb3a96f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FUNCTION_NAME = "compliance_log_immutable_guard"
_TRIGGER_NAME = "compliance_log_immutable_guard_trigger"


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {_FUNCTION_NAME}() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION
                'compliance_log is immutable: % on row id=% is not '
                'permitted (retention purges must go through '
                'ComplianceLogService.purge_older_than(), which '
                'explicitly disables this guard around its one '
                'intentional delete)',
                TG_OP, OLD.id;
        END;
        $$ LANGUAGE plpgsql;
        """,
    )

    op.execute(
        f"""
        CREATE TRIGGER {_TRIGGER_NAME}
            BEFORE UPDATE OR DELETE ON compliance_log
            FOR EACH ROW
            EXECUTE FUNCTION {_FUNCTION_NAME}();
        """,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(f"DROP TRIGGER IF EXISTS {_TRIGGER_NAME} ON compliance_log")
    op.execute(f"DROP FUNCTION IF EXISTS {_FUNCTION_NAME}()")
