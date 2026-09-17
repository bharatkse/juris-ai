"""
E2E: compliance_log's UPDATE/DELETE denial is enforced by two
independent layers -- a DB-level GRANT restriction (migration
dd110a14caf1_restrict_compliance_log_to_insert_.py, REVOKEs UPDATE/
DELETE from APP_DB_USER / juris_ai_app) and a DB-level trigger
(migration 48e4b24358b7_add_compliance_log_immutability_.py, blocks
UPDATE/DELETE unconditionally for every role, including the
admin/owner/superuser role the trigger-only test in
test_compliance_log_immutability.py exercises).

This file isolates each layer by removing the OTHER one and confirming
the remaining layer still blocks the write on its own -- not just that
both layers happen to agree when both are active, which wouldn't prove
either is independently load-bearing:

- Trigger disabled (via the admin role, which alone has that
  privilege) -> the restricted runtime role (session_factory /
  APP_DB_USER) is still denied, by the GRANT alone.
- (The symmetric case -- GRANT alone in place, trigger doing the
  blocking -- is what test_compliance_log_immutability.py already
  proves against the admin/owner/superuser role, for which the GRANT
  restriction has no effect at all; there is no role in this project
  for which the trigger is disabled while the GRANT still applies, the
  other way round, since only the admin role can disable the trigger
  and the admin role is also exempt from GRANT-level restriction.)

Requires the real Postgres/Redis docker compose services running
(`make docker-up`), with migrations applied through dd110a14caf1, and
the local juris_ai_app role provisioned (deploy/docker/init/postgres/
01-create-app-role.sh -- see that script's docstring for how to pick
this up on an already-existing local Postgres volume). Skips itself,
rather than failing, when APP_DB_USER isn't configured -- this is
local-dev-only role separation, not something every environment this
test suite might run against is expected to have.

Run via `make test-e2e`.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from adapters.persistence.sqlalchemy.models.compliance_log import ComplianceLog
from adapters.persistence.sqlalchemy.repositories.compliance_log import (
    ComplianceLogRepository,
)
from adapters.persistence.sqlalchemy.session import (
    admin_session_factory,
    dispose_admin_engine,
    dispose_engine,
    session_factory,
)
from config.settings import get_settings
from core.enums import ActorTypeEnum, ComplianceEventTypeEnum

pytestmark = pytest.mark.skipif(
    not get_settings().database.APP_DB_USER,
    reason=(
        "APP_DB_USER not configured -- this project's local-dev-only "
        "role separation isn't set up in this environment."
    ),
)


def _entry() -> ComplianceLog:
    return ComplianceLog(
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


@pytest.mark.asyncio
async def test_grant_alone_blocks_the_restricted_role_with_the_trigger_disabled() -> None:
    """
    Isolate the GRANT-level layer: with the trigger deliberately
    disabled (something only the admin role can even do), the
    restricted runtime role (juris_ai_app, via session_factory) must
    still be denied UPDATE/DELETE on compliance_log -- proving the
    REVOKE from dd110a14caf1 is independently load-bearing, not
    redundant with the trigger.
    """

    await dispose_admin_engine()
    await dispose_engine()

    async with admin_session_factory() as admin_session:
        repository = ComplianceLogRepository(session=admin_session)
        row = await repository.create(_entry())
        row_id = row.id
        await admin_session.commit()

        await repository.disable_immutability_guard()
        await admin_session.commit()

    try:
        async with session_factory() as app_session:
            with pytest.raises(DBAPIError, match="permission denied"):
                await app_session.execute(
                    text("UPDATE compliance_log SET payload = '{}' WHERE id = :id"),
                    {"id": row_id},
                )
            await app_session.rollback()

            with pytest.raises(DBAPIError, match="permission denied"):
                await app_session.execute(
                    text("DELETE FROM compliance_log WHERE id = :id"),
                    {"id": row_id},
                )
            await app_session.rollback()

        # Confirm INSERT/SELECT still work for the restricted role --
        # this is a denial of UPDATE/DELETE specifically, not a role
        # that's broken outright.
        async with session_factory() as app_session:
            selected = (
                await app_session.execute(
                    text("SELECT id FROM compliance_log WHERE id = :id"),
                    {"id": row_id},
                )
            ).scalar_one()
            assert selected == row_id

    finally:
        # Trigger is still disabled at this point (nothing in the try
        # block re-enabled it) -- delete the test row first, while
        # that's still true, then re-enable. Re-enabling before
        # deleting would just reproduce the same "immutable" failure
        # this test isn't about, against the admin/owner role's own
        # DELETE.
        async with admin_session_factory() as admin_session:
            repository = ComplianceLogRepository(session=admin_session)
            await admin_session.execute(
                text("DELETE FROM compliance_log WHERE id = :id"),
                {"id": row_id},
            )
            await repository.enable_immutability_guard()
            await admin_session.commit()
