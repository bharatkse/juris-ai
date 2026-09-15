"""
Manually purge compliance_log rows older than the configured
retention period.

This script is the ONLY thing in this codebase that ever calls
ComplianceLogService.purge_older_than() -- there is no scheduled job,
cron, or background task anywhere that runs a purge automatically.
Nothing happens unless a human runs this script deliberately, and
nothing happens even then unless COMPLIANCE_LOG_RETENTION_DAYS has
been set explicitly (it defaults to None -- retain indefinitely).

Do not set COMPLIANCE_LOG_RETENTION_DAYS, and do not run this script,
without confirmed legal/compliance retention requirements for your
jurisdiction and matter types. This is destructive and irreversible:
a real DELETE against compliance_log, not a soft delete or archive.

compliance_log also carries a DB-level BEFORE UPDATE OR DELETE trigger
(migration 48e4b24358b7_add_compliance_log_immutability_.py) that
unconditionally blocks UPDATE/DELETE -- including for this script's
own DB role, even though that role owns the table. This script is the
only place that deliberately disables that trigger (immediately before
its one intentional DELETE, re-enabled immediately after, see main()
below) -- a second, structural reason nothing else in this codebase
can accidentally modify or delete a compliance_log row.

DB role, explicit decision: this script uses admin_session_factory
(the schema-owning admin/migration role, DB_USER), not the app's
normal session_factory (the restricted runtime role, APP_DB_USER,
introduced by the local role-separation work -- see deploy/docker/
init/postgres/01-create-app-role.sh). It has to: disabling the
immutability trigger above (ALTER TABLE ... DISABLE TRIGGER) requires
table ownership, which the restricted role deliberately does not have.
This is a script an operator runs deliberately and rarely, not
request-handling code, so running it as the admin role does not
reintroduce the exposure the role split exists to close.

Run: PYTHONPATH=src python scripts/python/purge_compliance_log.py --yes
(omit --yes for a dry run that reports what WOULD be deleted without
deleting anything).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta

from adapters.persistence.sqlalchemy.repositories.compliance_log import (
    ComplianceLogRepository,
)
from adapters.persistence.sqlalchemy.session import admin_session_factory as session_factory
from application.services.compliance_log import ComplianceLogService
from config.settings import get_settings


async def main(*, confirmed: bool) -> int:
    settings = get_settings()
    retention_days = settings.compliance.COMPLIANCE_LOG_RETENTION_DAYS

    if retention_days is None:
        print(
            "COMPLIANCE_LOG_RETENTION_DAYS is not set (None = retain "
            "indefinitely). Refusing to purge -- nothing was deleted. "
            "Set it explicitly, only after confirming a real "
            "legal/compliance retention requirement, to enable this.",
        )
        return 1

    cutoff = datetime.now(UTC) - timedelta(days=retention_days)

    if not confirmed:
        async with session_factory() as session:
            repository = ComplianceLogRepository(session=session)
            would_delete = await repository.count_older_than(cutoff=cutoff)

        print(
            f"Dry run: {would_delete} compliance_log row(s) older than "
            f"{retention_days} day(s) (cutoff: {cutoff.isoformat()}) would "
            f"be permanently deleted. Nothing was deleted. Re-run with "
            f"--yes to actually purge.",
        )
        return 0

    async with session_factory() as session:
        repository = ComplianceLogRepository(session=session)
        service = ComplianceLogService(session=session, repository=repository)

        # The DB-level immutability trigger (migration
        # 48e4b24358b7_add_compliance_log_immutability_.py) blocks
        # this DELETE unconditionally, including for this script's own
        # (owner/superuser) DB role -- see that migration's docstring.
        # Disabling it is the one deliberate, explicit escape hatch;
        # the try/finally guarantees it is re-enabled even if the
        # purge itself fails. Disable, delete, and re-enable all run
        # as ONE uncommitted transaction here (committed together
        # below) specifically to minimize ALTER TABLE ... DISABLE
        # TRIGGER's catalog-level (not session-scoped) exposure window
        # -- no other connection can observe the trigger as disabled
        # until this transaction commits, by which point it is already
        # re-enabled again.
        try:
            await repository.disable_immutability_guard()
            deleted_count = await service.purge_older_than(retention_days=retention_days)
        finally:
            await repository.enable_immutability_guard()

        await session.commit()

    print(
        f"Purged {deleted_count} compliance_log row(s) older than "
        f"{retention_days} day(s) (cutoff: {cutoff.isoformat()}).",
    )

    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Purge compliance_log rows older than the configured retention "
            "period. Destructive and irreversible -- see this script's "
            "module docstring before running it."
        ),
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        dest="confirmed",
        help=(
            "Actually perform the deletion. Without this flag, the script "
            "only reports the configured retention setting and exits "
            "without touching the database."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(asyncio.run(main(confirmed=args.confirmed)))
