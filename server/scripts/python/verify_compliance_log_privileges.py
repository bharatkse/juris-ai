"""
Verify compliance_log's DB-level privilege restrictions actually work,
against a properly-scoped (non-owner, non-superuser) role -- not
against this project's admin/migration role (DB_USER), which is
confirmed to be both the table's owner and a Postgres superuser in the
local dev database, and therefore bypasses ACL enforcement entirely
regardless of what has been REVOKEd (see the migrations this verifies:
9338dbb3a96f_restrict_compliance_log_to_insert_.py and
dd110a14caf1_restrict_compliance_log_to_insert_.py, whose docstrings
have the full explanation and the same reproduction this script
automates).

Note this project now has a real, non-owner, NOSUPERUSER runtime role
too -- APP_DB_USER / juris_ai_app, from the local role-separation work
(deploy/docker/init/postgres/01-create-app-role.sh) -- which
dd110a14caf1's REVOKE targets directly and does actually restrict.
This script still verifies against a disposable scratch role rather
than juris_ai_app itself: it's self-contained (no dependency on that
role already existing) and disposable (creates and drops its own role
and test row every run). The live grant-vs-trigger proof against the
real juris_ai_app role specifically lives in
tests/e2e/test_compliance_log_immutability.py instead.

What this proves: the REVOKE is real, correct SQL that DOES block
UPDATE/DELETE and DOES allow INSERT/SELECT for any role it actually
applies to (i.e. any role that isn't the table owner or a superuser).
It does not, and cannot, prove anything about the admin/migration
role's own behavior, because REVOKE structurally cannot restrict an
owner or a superuser -- that isn't a gap in this script, it's how
PostgreSQL privilege checks work.

Creates a temporary, unprivileged scratch role, runs INSERT/SELECT/
UPDATE/DELETE against compliance_log as that role, reports pass/fail
for each, and drops the scratch role and its test row again -- leaves
no permanent state behind either way.

DB role, explicit decision: this script connects via
settings.admin_async_database_url (DB_USER), not
settings.async_database_url (APP_DB_USER, the restricted runtime
role introduced by the local role-separation work). It has to: CREATE
ROLE and GRANT/REVOKE on a table this script's own connection doesn't
own both require privilege the restricted role deliberately does not
have.

Run: PYTHONPATH=src python scripts/python/verify_compliance_log_privileges.py
Requires a running Postgres reachable via config.settings (i.e. the
same DB this project's migrations/app already point at) and a role
with permission to CREATE ROLE (the admin/migration role, in this
project's dev setup).
"""

from __future__ import annotations

import asyncio
import secrets
import sys

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from config.settings import get_settings

SCRATCH_ROLE = "compliance_log_privilege_check"
TEST_ROW_ID = "cplg_privilegecheck00000000000000"


async def main() -> int:
    settings = get_settings()
    admin_url = settings.admin_async_database_url

    admin_engine = create_async_engine(admin_url)

    results: dict[str, bool] = {}

    try:
        scratch_password = secrets.token_urlsafe(24)

        async with admin_engine.begin() as conn:
            await conn.execute(text(f'DROP ROLE IF EXISTS "{SCRATCH_ROLE}"'))
            # CREATE ROLE ... PASSWORD is DDL -- Postgres does not
            # accept a bind parameter there the way DML statements do
            # (confirmed: parameterizing it makes the whole statement
            # fail silently under asyncpg's extended query protocol).
            # scratch_password is script-generated (secrets.token_urlsafe),
            # never user input, so direct interpolation here is safe.
            await conn.execute(
                text(
                    f'CREATE ROLE "{SCRATCH_ROLE}" LOGIN '
                    f"PASSWORD '{scratch_password}' NOSUPERUSER",
                ),
            )
            await conn.execute(
                text(f'GRANT INSERT, SELECT ON compliance_log TO "{SCRATCH_ROLE}"'),
            )
            # The scratch role must NOT inherit owner/superuser bypass
            # from anywhere -- explicit, matches the REVOKE this is
            # verifying.
            await conn.execute(
                text(f'REVOKE UPDATE, DELETE ON compliance_log FROM "{SCRATCH_ROLE}"'),
            )

        scratch_url = (
            admin_url.split("://", 1)[0]
            + f"://{SCRATCH_ROLE}:{scratch_password}@"
            + admin_url.split("@", 1)[1]
        )
        scratch_engine = create_async_engine(scratch_url)

        try:
            results["INSERT (expected: succeeds)"] = await _try(
                scratch_engine,
                text(
                    "INSERT INTO compliance_log "
                    "(id, user_id, tenant_id, actor_type, event_type, payload, "
                    "created_at, updated_at) "
                    "VALUES (:id, 'user_1', 'user_1', 'USER', 'REQUEST_RECEIVED', "
                    "'{}', now(), now())",
                ),
                {"id": TEST_ROW_ID},
                expect_success=True,
            )
            results["SELECT (expected: succeeds)"] = await _try(
                scratch_engine,
                text("SELECT id FROM compliance_log WHERE id = :id"),
                {"id": TEST_ROW_ID},
                expect_success=True,
            )
            results["UPDATE (expected: denied)"] = await _try(
                scratch_engine,
                text("UPDATE compliance_log SET payload = '{}' WHERE id = :id"),
                {"id": TEST_ROW_ID},
                expect_success=False,
            )
            results["DELETE (expected: denied)"] = await _try(
                scratch_engine,
                text("DELETE FROM compliance_log WHERE id = :id"),
                {"id": TEST_ROW_ID},
                expect_success=False,
            )
        finally:
            await scratch_engine.dispose()

    finally:
        async with admin_engine.begin() as conn:
            # Bug found while verifying the role-separation work (not
            # introduced by it): migration 48e4b24358b7 added a BEFORE
            # UPDATE OR DELETE trigger on compliance_log that blocks
            # every role unconditionally, including this admin
            # connection -- a plain DELETE here has failed with
            # "compliance_log is immutable" ever since that migration
            # landed, leaving TEST_ROW_ID stuck with no way for this
            # script to clean it up on its own. Disable/re-enable
            # around the one intentional DELETE, same escape hatch
            # scripts/python/purge_compliance_log.py uses (see
            # ComplianceLogRepository.disable_immutability_guard()).
            await conn.execute(
                text(
                    "ALTER TABLE compliance_log DISABLE TRIGGER "
                    "compliance_log_immutable_guard_trigger",
                ),
            )
            await conn.execute(
                text("DELETE FROM compliance_log WHERE id = :id"),
                {"id": TEST_ROW_ID},
            )
            await conn.execute(
                text(
                    "ALTER TABLE compliance_log ENABLE TRIGGER "
                    "compliance_log_immutable_guard_trigger",
                ),
            )
            role_exists = (
                await conn.execute(
                    text("SELECT 1 FROM pg_roles WHERE rolname = :role"),
                    {"role": SCRATCH_ROLE},
                )
            ).first()
            if role_exists:
                await conn.execute(
                    text(f'REVOKE ALL ON compliance_log FROM "{SCRATCH_ROLE}"'),
                )
                await conn.execute(text(f'DROP ROLE "{SCRATCH_ROLE}"'))

        await admin_engine.dispose()

    print("compliance_log privilege verification (scratch, non-owner, NOSUPERUSER role):")
    all_passed = True
    for label, passed in results.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
        all_passed = all_passed and passed

    return 0 if all_passed else 1


async def _try(engine, statement, params, *, expect_success: bool) -> bool:
    try:
        async with engine.begin() as conn:
            await conn.execute(statement, params)
        return expect_success

    except DBAPIError as exc:
        if "permission denied" in str(exc).lower():
            return not expect_success
        raise


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
