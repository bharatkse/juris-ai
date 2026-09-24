"""
Unit tests for ComplianceLogRepository -- real test-database rows,
real DELETE, per this repository suite's usual convention (db_session
is a real transactional session rolled back after each test).

Focus: delete_older_than()/count_older_than() -- the two methods
backing the retention purge -- actually respect the cutoff boundary
(delete/count strictly older rows, never rows at or after cutoff).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from adapters.persistence.sqlalchemy.models.compliance_log import ComplianceLog
from core.enums import ActorTypeEnum, ComplianceEventTypeEnum


def _build_entry(*, created_at: datetime) -> ComplianceLog:
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
    # created_at has a server-side default (utcnow) via TimestampMixin
    # -- overridden explicitly here so the fixture can place rows on
    # either side of a cutoff deterministically.
    entry.created_at = created_at
    return entry


@pytest.mark.asyncio
async def test_delete_older_than_removes_only_rows_before_cutoff(
    compliance_log_repository,
    db_session,
) -> None:
    now = datetime.now(UTC)

    old_row = await compliance_log_repository.create(
        _build_entry(created_at=now - timedelta(days=100)),
    )
    recent_row = await compliance_log_repository.create(
        _build_entry(created_at=now - timedelta(days=1)),
    )

    cutoff = now - timedelta(days=30)

    deleted_count = await compliance_log_repository.delete_older_than(cutoff=cutoff)

    assert deleted_count == 1

    remaining = await compliance_log_repository.list_for_user(
        user_id="user_1",
        start=now - timedelta(days=200),
        end=now + timedelta(days=1),
    )
    remaining_ids = {row.id for row in remaining}

    assert old_row.id not in remaining_ids
    assert recent_row.id in remaining_ids


@pytest.mark.asyncio
async def test_delete_older_than_deletes_nothing_when_no_rows_qualify(
    compliance_log_repository,
) -> None:
    now = datetime.now(UTC)

    await compliance_log_repository.create(
        _build_entry(created_at=now - timedelta(days=1)),
    )

    deleted_count = await compliance_log_repository.delete_older_than(
        cutoff=now - timedelta(days=30),
    )

    assert deleted_count == 0


@pytest.mark.asyncio
async def test_count_older_than_matches_what_delete_would_remove(
    compliance_log_repository,
) -> None:
    now = datetime.now(UTC)

    await compliance_log_repository.create(_build_entry(created_at=now - timedelta(days=100)))
    await compliance_log_repository.create(_build_entry(created_at=now - timedelta(days=90)))
    await compliance_log_repository.create(_build_entry(created_at=now - timedelta(days=1)))

    cutoff = now - timedelta(days=30)

    counted = await compliance_log_repository.count_older_than(cutoff=cutoff)
    deleted_count = await compliance_log_repository.delete_older_than(cutoff=cutoff)

    assert counted == 2
    assert deleted_count == 2
