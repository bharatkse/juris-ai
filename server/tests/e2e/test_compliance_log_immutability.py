"""
E2E: compliance_log's DB-level immutability trigger, over the real
Postgres database and the admin/migration DB role (DB_USER -- owner
and superuser).

Unlike scripts/python/verify_compliance_log_privileges.py (which
proves the REVOKE-based restriction works against a properly-scoped,
non-owner, non-superuser role -- migration 9338dbb3a96f cannot
restrict the admin/migration role, which is both owner and superuser),
this test proves the trigger-based guard (migration
48e4b24358b7_add_compliance_log_immutability_.py) blocks UPDATE/DELETE
unconditionally -- including for that same owner/superuser role, using
admin_session_factory (not this project's normal, restricted-runtime-role
session_factory -- see the local role-separation work,
deploy/docker/init/postgres/01-create-app-role.sh, and
test_grant_and_trigger_are_independent_layers.py below for the
restricted role's own grant-level proof). And it proves the purge
script's disable/enable sequence
(ComplianceLogRepository.disable_immutability_guard()/
enable_immutability_guard(), called from scripts/python/
purge_compliance_log.py) is the one thing that actually gets past it
-- disable_immutability_guard() itself needs admin_session_factory too,
since ALTER TABLE ... DISABLE TRIGGER requires table ownership.

Requires the real Postgres/Redis docker compose services running
(`./setup.sh --install --dependency postgres
--dependency redis`), with migrations applied through 48e4b24358b7.
Run via `make test-e2e`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from adapters.persistence.sqlalchemy.models.compliance_log import ComplianceLog
from adapters.persistence.sqlalchemy.repositories.compliance_log import (
    ComplianceLogRepository,
)
from adapters.persistence.sqlalchemy.session import admin_session_factory as session_factory
from adapters.persistence.sqlalchemy.session import dispose_admin_engine as dispose_engine
from application.services.compliance_log import ComplianceLogService
from core.enums import ActorTypeEnum, ComplianceEventTypeEnum


def _entry(*, created_at: datetime) -> ComplianceLog:
    entry = ComplianceLog(
        request_id=None,
        conversation_id=None,
        conversation_event_id=None,
        thread_id=None,
        user_id="user_1",
        tenant_id="user_1",
        actor_type=ActorTypeEnum.USER,
        event_type=ComplianceEventTypeEnum.REQUEST_RECEIVED,
        payload={"message_hash": "x", "message_length": 1},
    )
    entry.created_at = created_at
    return entry


@pytest.mark.asyncio
async def test_trigger_blocks_update_and_delete_even_for_the_app_role() -> None:
    """
    The core guarantee: even this project's own configured DB role
    (confirmed elsewhere to be both compliance_log's owner AND a
    Postgres superuser, which is exactly why the REVOKE-based
    migration alone cannot restrict it) gets a hard failure attempting
    UPDATE or DELETE here, with the trigger's own explicit message --
    not a silent success.
    """

    # session_factory's pooled connections are bound to whichever event
    # loop was running at checkout time; pytest-asyncio hands each test
    # function its own fresh loop, so a connection pooled by an earlier
    # test would otherwise leak across loops here (mirrors tests/e2e/
    # conftest.py's e2e_client fixture, which does the same before/after
    # each test for the same reason -- this test has no such fixture of
    # its own since it never goes through the HTTP layer).
    await dispose_engine()

    async with session_factory() as session:
        repository = ComplianceLogRepository(session=session)
        row = await repository.create(_entry(created_at=datetime.now(UTC)))
        row_id = row.id  # captured before commit/rollback expire the instance
        await session.commit()

        with pytest.raises(DBAPIError, match="compliance_log is immutable"):
            await session.execute(
                text("UPDATE compliance_log SET payload = '{}' WHERE id = :id"),
                {"id": row_id},
            )
        await session.rollback()

        with pytest.raises(DBAPIError, match="compliance_log is immutable"):
            await session.execute(
                text("DELETE FROM compliance_log WHERE id = :id"),
                {"id": row_id},
            )
        await session.rollback()

    # Cleanup, through the same disable/enable escape hatch the purge
    # script uses -- proven by the next test, used here only to leave
    # no test data behind.
    async with session_factory() as session:
        repository = ComplianceLogRepository(session=session)
        await repository.disable_immutability_guard()
        await repository.delete_older_than(cutoff=datetime.now(UTC) + timedelta(seconds=1))
        await repository.enable_immutability_guard()
        await session.commit()


@pytest.mark.asyncio
async def test_purge_script_mechanism_deletes_through_the_trigger_and_restores_it() -> None:
    """
    End-to-end proof of the exact sequence scripts/python/
    purge_compliance_log.py runs: disable_immutability_guard() ->
    ComplianceLogService.purge_older_than() -> enable_immutability_guard()
    within one committed transaction. Confirms the old row is actually
    gone, AND that the guard is genuinely back in force afterward (not
    left disabled) by attempting a fresh raw DELETE once the sequence
    completes.
    """

    await dispose_engine()

    now = datetime.now(UTC)

    async with session_factory() as session:
        repository = ComplianceLogRepository(session=session)
        old_row = await repository.create(_entry(created_at=now - timedelta(days=400)))
        recent_row = await repository.create(_entry(created_at=now - timedelta(days=1)))
        old_row_id = old_row.id
        recent_row_id = recent_row.id
        await session.commit()

    async with session_factory() as session:
        repository = ComplianceLogRepository(session=session)
        service = ComplianceLogService(session=session, repository=repository)

        try:
            await repository.disable_immutability_guard()
            deleted_count = await service.purge_older_than(retention_days=30)
        finally:
            await repository.enable_immutability_guard()

        await session.commit()

    assert deleted_count >= 1

    async with session_factory() as session:
        remaining = (
            (
                await session.execute(
                    text("SELECT id FROM compliance_log WHERE id IN (:old, :recent)"),
                    {"old": old_row_id, "recent": recent_row_id},
                )
            )
            .scalars()
            .all()
        )

    assert old_row_id not in remaining
    assert recent_row_id in remaining

    # The guard must be back in force -- a raw DELETE right after the
    # purge sequence completed must fail exactly like before it ran.
    async with session_factory() as session:
        with pytest.raises(DBAPIError, match="compliance_log is immutable"):
            await session.execute(
                text("DELETE FROM compliance_log WHERE id = :id"),
                {"id": recent_row_id},
            )
        await session.rollback()

    # Cleanup.
    async with session_factory() as session:
        repository = ComplianceLogRepository(session=session)
        await repository.disable_immutability_guard()
        await repository.delete_older_than(cutoff=now + timedelta(seconds=1))
        await repository.enable_immutability_guard()
        await session.commit()
