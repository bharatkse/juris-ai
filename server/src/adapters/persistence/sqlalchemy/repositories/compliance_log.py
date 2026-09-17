"""
Compliance log repository.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.models.compliance_log import ComplianceLog
from adapters.persistence.sqlalchemy.repositories.base import BaseRepository

if TYPE_CHECKING:
    from core.enums import ComplianceEventTypeEnum


class ComplianceLogRepository(BaseRepository[ComplianceLog]):
    """
    Persistence for the compliance log.

    Insert-only for normal operation -- no update() exists, and the
    one deliberate exception to "no delete either" is
    delete_older_than(), which exists solely to back the explicit,
    opt-in retention purge (ComplianceLogService.purge_older_than()).
    See ComplianceLog's docstring on immutability for why this table
    doesn't otherwise allow deletes. This repository does not decide
    what belongs in a row (payload shape, the no-raw-content rule) or
    whether/when a purge should run -- that is ComplianceLogService's
    job; this class only persists, queries, and (on explicit request)
    deletes.

    A real DB-level BEFORE UPDATE OR DELETE trigger (migration
    48e4b24358b7_add_compliance_log_immutability_.py) additionally
    blocks UPDATE/DELETE unconditionally -- including for this table's
    owner/superuser role, which the earlier REVOKE-based migration
    (9338dbb3a96f) cannot restrict (see its docstring). delete_older_than()
    above will therefore fail against a real database unless the
    trigger has first been disabled via disable_immutability_guard()
    below -- see scripts/python/purge_compliance_log.py, the only
    caller that does this.
    """

    _model = ComplianceLog

    # Must match the trigger name the migration creates
    # (48e4b24358b7_add_compliance_log_immutability_.py) -- kept here,
    # next to the only methods that reference it, rather than in the
    # migration itself, since a migration's identifiers are meant to
    # be a one-time historical record, not imported by application
    # code.
    _IMMUTABILITY_TRIGGER = "compliance_log_immutable_guard_trigger"

    def __init__(
        self,
        *,
        session: AsyncSession,
    ) -> None:
        super().__init__(session=session)

    async def create(
        self,
        entity: ComplianceLog,
    ) -> ComplianceLog:
        """
        Persist a compliance log entry.
        """

        return await self.persist(entity)

    async def list_for_user(
        self,
        *,
        user_id: str,
        start: datetime,
        end: datetime,
        event_type: ComplianceEventTypeEnum | None = None,
        limit: int = 500,
    ) -> list[ComplianceLog]:
        """
        The core discovery query: "everything the system knew and
        decided for user X between date A and B" -- a single scan on
        ix_compliance_log_user_created, chronological order, no joins.
        Follow-up detail (retrieved chunk text, approval reasoning,
        full response content) resolves separately through the
        identifiers each row's payload carries -- see
        ComplianceLogService's module docstring.
        """

        statement = (
            self.select()
            .where(
                self._model.user_id == user_id,
                self._model.created_at >= start,
                self._model.created_at <= end,
            )
            .order_by(
                self._model.created_at.asc(),
            )
            .limit(limit)
        )

        if event_type is not None:
            statement = statement.where(self._model.event_type == event_type)

        result = await self._session.execute(statement)

        return list(result.scalars().all())

    async def count_older_than(
        self,
        *,
        cutoff: datetime,
    ) -> int:
        """
        Read-only count of rows delete_older_than(cutoff) would
        remove -- backs a dry-run report (scripts/python/
        purge_compliance_log.py without --yes) so an operator can see
        the impact before ever calling the destructive method.
        """

        statement = (
            select(func.count())
            .select_from(self._model)
            .where(
                self._model.created_at < cutoff,
            )
        )

        result = await self._session.execute(statement)

        return int(result.scalar_one())

    async def delete_older_than(
        self,
        *,
        cutoff: datetime,
    ) -> int:
        """
        Permanently delete every row with created_at < cutoff.

        Bulk DELETE, not a load-then-delete-each loop -- rows can
        number in the millions once real retention data accumulates.
        No caller in this codebase invokes this except
        ComplianceLogService.purge_older_than(), which is itself never
        called automatically -- see that method's docstring for the
        explicit-opt-in guard that makes exposing this safe.

        synchronize_session=False: this is a pure bulk operation, not
        one that needs the ORM to keep any already-loaded in-session
        objects consistent with rows it just deleted (the caller isn't
        expected to keep using stale ComplianceLog instances after a
        purge) -- the default "evaluate" strategy instead tries to
        re-evaluate the WHERE clause in Python against every object
        already in the session's identity map, which breaks here with
        a naive-vs-aware datetime comparison the instant any row's
        created_at has round-tripped through the DB driver.
        """

        statement = (
            delete(self._model)
            .where(self._model.created_at < cutoff)
            .execution_options(synchronize_session=False)
        )

        result = await self._session.execute(statement)

        # AsyncSession.execute()'s declared return type is the generic
        # Result[Any]; a DELETE actually returns a CursorResult, which
        # does carry .rowcount at runtime -- mypy can't see that from
        # the generic signature alone.
        return result.rowcount or 0  # type: ignore[attr-defined]

    async def disable_immutability_guard(self) -> None:
        """
        Disable the DB-level immutability trigger so the caller's
        NEXT statement on this connection (expected to be
        delete_older_than()) can actually succeed.

        ALTER TABLE ... DISABLE TRIGGER is catalog-level, not
        connection/session-scoped: every connection against this
        database sees the trigger as disabled until
        enable_immutability_guard() runs, not just this one. Callers
        must re-enable it as soon as possible (a try/finally, not a
        best-effort cleanup) -- see scripts/python/
        purge_compliance_log.py, the only caller.
        """

        await self._session.execute(
            text(f"ALTER TABLE compliance_log DISABLE TRIGGER {self._IMMUTABILITY_TRIGGER}"),
        )

    async def enable_immutability_guard(self) -> None:
        """
        Re-enable the trigger disable_immutability_guard() turned off.
        """

        await self._session.execute(
            text(f"ALTER TABLE compliance_log ENABLE TRIGGER {self._IMMUTABILITY_TRIGGER}"),
        )

    async def list_for_request(
        self,
        *,
        request_id: object,
    ) -> list[ComplianceLog]:
        """
        Full reconstruction of one request/turn -- every row sharing
        its request_id, in chronological order. Single index
        (ix_compliance_log_request_id).
        """

        statement = (
            self.select()
            .where(self._model.request_id == request_id)
            .order_by(self._model.created_at.asc())
        )

        result = await self._session.execute(statement)

        return list(result.scalars().all())
