"""
Unit tests for UserMemoryRepository -- the tenant-isolation boundary for
user memories.

Runs against the suite's real (SQLite) test database, so everything here
is limited to what SQLite can execute: scoping, visibility, expiry and
deletion. Vector similarity (`<=>`) is pgvector-only and is covered,
against real Postgres, by tests/e2e/test_user_memory_isolation.py.

The first test is structural on purpose: it fails if anyone adds a
repository method that does not take a required, keyword-only user_id,
which is how an unscoped query would sneak in.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.models.user_memory import UserMemory
from adapters.persistence.sqlalchemy.repositories.user_memory import (
    UserMemoryRepository,
)
from core.enums import UserMemoryKindEnum, UserMemoryStatusEnum

USER_A = "user_a"
USER_B = "user_b"

EMBEDDING = [0.0] * 384

NOW = datetime(2026, 9, 21, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def repository(db_session: AsyncSession) -> UserMemoryRepository:
    return UserMemoryRepository(session=db_session)


async def _add(
    repository: UserMemoryRepository,
    *,
    user_id: str,
    content: str = "prefers concise answers",
    content_hash: str | None = None,
    kind: UserMemoryKindEnum = UserMemoryKindEnum.PREFERENCE,
    status: UserMemoryStatusEnum = UserMemoryStatusEnum.ACTIVE,
    expires_at: datetime | None = None,
) -> UserMemory:
    return await repository.add(
        user_id=user_id,
        kind=kind,
        content=content,
        content_hash=content_hash or f"hash:{content}",
        embedding=EMBEDDING,
        embedding_model="test-model",
        confidence=1.0,
        last_used_at=NOW,
        expires_at=expires_at or NOW + timedelta(days=120),
        status=status,
    )


def test_every_public_method_requires_keyword_only_user_id() -> None:
    public = {
        name: member
        for name, member in vars(UserMemoryRepository).items()
        if not name.startswith("_")
    }

    assert public, "expected UserMemoryRepository to define public methods"

    for name, member in public.items():
        assert inspect.iscoroutinefunction(member), (
            f"{name} is public but is not an async repository method; "
            "every public member must be a user-scoped query."
        )

        parameter = inspect.signature(member).parameters.get("user_id")

        assert parameter is not None, f"{name} has no user_id parameter"
        assert (
            parameter.kind is inspect.Parameter.KEYWORD_ONLY
        ), f"{name}: user_id must be keyword-only"
        assert (
            parameter.default is inspect.Parameter.empty
        ), f"{name}: user_id must be required, not defaulted"


@pytest.mark.parametrize("bad_user_id", ["", None])
async def test_empty_user_id_is_rejected_not_treated_as_a_wildcard(
    repository: UserMemoryRepository,
    bad_user_id: str | None,
) -> None:
    with pytest.raises(ValueError, match="user_id is required"):
        await repository.get(user_id=bad_user_id, memory_id="umem_x")  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="user_id is required"):
        await repository.delete_all(user_id=bad_user_id)  # type: ignore[arg-type]


async def test_get_never_returns_another_users_memory(
    repository: UserMemoryRepository,
) -> None:
    memory = await _add(repository, user_id=USER_A)

    assert await repository.get(user_id=USER_A, memory_id=memory.id) is not None
    assert await repository.get(user_id=USER_B, memory_id=memory.id) is None


async def test_delete_cannot_remove_another_users_memory(
    repository: UserMemoryRepository,
) -> None:
    memory = await _add(repository, user_id=USER_A)

    assert await repository.delete(user_id=USER_B, memory_id=memory.id) is False
    assert await repository.get(user_id=USER_A, memory_id=memory.id) is not None

    assert await repository.delete(user_id=USER_A, memory_id=memory.id) is True
    assert await repository.get(user_id=USER_A, memory_id=memory.id) is None


async def test_delete_all_removes_only_the_callers_memories(
    repository: UserMemoryRepository,
) -> None:
    await _add(repository, user_id=USER_A, content="a1")
    await _add(repository, user_id=USER_A, content="a2")
    await _add(repository, user_id=USER_B, content="b1")

    assert await repository.delete_all(user_id=USER_A) == 2

    assert await repository.count_visible(user_id=USER_A, now=NOW) == 0
    assert await repository.count_visible(user_id=USER_B, now=NOW) == 1


async def test_list_visible_is_scoped_and_hides_expired_and_superseded(
    repository: UserMemoryRepository,
) -> None:
    visible = await _add(repository, user_id=USER_A, content="visible")
    pending = await _add(
        repository,
        user_id=USER_A,
        content="pending",
        status=UserMemoryStatusEnum.PENDING,
    )
    await _add(
        repository,
        user_id=USER_A,
        content="expired",
        expires_at=NOW - timedelta(seconds=1),
    )
    await _add(
        repository,
        user_id=USER_A,
        content="superseded",
        status=UserMemoryStatusEnum.SUPERSEDED,
    )
    await _add(repository, user_id=USER_B, content="someone else's")

    rows = await repository.list_visible(user_id=USER_A, now=NOW, limit=50)

    assert {row.id for row in rows} == {visible.id, pending.id}
    assert all(row.user_id == USER_A for row in rows)
    assert await repository.count_visible(user_id=USER_A, now=NOW) == 2


async def test_expiry_boundary_is_exclusive(
    repository: UserMemoryRepository,
) -> None:
    await _add(repository, user_id=USER_A, content="exactly at expiry", expires_at=NOW)

    assert await repository.count_visible(user_id=USER_A, now=NOW) == 0
    assert (
        await repository.count_visible(
            user_id=USER_A,
            now=NOW - timedelta(seconds=1),
        )
        == 1
    )


async def test_live_by_kind_is_scoped_filters_kind_and_orders_by_recent_use(
    repository: UserMemoryRepository,
) -> None:
    older = await _add(
        repository,
        user_id=USER_A,
        content="profile older",
        kind=UserMemoryKindEnum.PROFILE,
    )
    older.last_used_at = NOW - timedelta(days=5)
    newer = await _add(
        repository,
        user_id=USER_A,
        content="profile newer",
        kind=UserMemoryKindEnum.PROFILE,
    )
    await _add(repository, user_id=USER_A, content="a preference")
    await _add(
        repository,
        user_id=USER_B,
        content="b profile",
        kind=UserMemoryKindEnum.PROFILE,
    )

    rows = await repository.list_live_by_kind(
        user_id=USER_A,
        kind=UserMemoryKindEnum.PROFILE,
        now=NOW,
        limit=10,
    )

    assert [row.id for row in rows] == [newer.id, older.id]


async def test_touch_only_affects_the_callers_rows(
    repository: UserMemoryRepository,
) -> None:
    memory = await _add(repository, user_id=USER_A)
    original_expiry = memory.expires_at
    later = NOW + timedelta(days=10)

    assert (
        await repository.touch(
            user_id=USER_B,
            memory_ids=[memory.id],
            last_used_at=later,
            expires_at=later + timedelta(days=120),
        )
        == 0
    )

    await repository.refresh(memory)
    assert memory.expires_at == original_expiry

    assert (
        await repository.touch(
            user_id=USER_A,
            memory_ids=[memory.id],
            last_used_at=later,
            expires_at=later + timedelta(days=120),
        )
        == 1
    )


async def test_touch_with_no_ids_is_a_noop(
    repository: UserMemoryRepository,
) -> None:
    assert (
        await repository.touch(
            user_id=USER_A,
            memory_ids=[],
            last_used_at=NOW,
            expires_at=NOW,
        )
        == 0
    )


async def test_set_status_cannot_change_another_users_memory(
    repository: UserMemoryRepository,
) -> None:
    memory = await _add(repository, user_id=USER_A)

    assert (
        await repository.set_status(
            user_id=USER_B,
            memory_id=memory.id,
            status=UserMemoryStatusEnum.SUPERSEDED,
        )
        is False
    )

    await repository.refresh(memory)
    assert memory.status == UserMemoryStatusEnum.ACTIVE.value

    assert (
        await repository.set_status(
            user_id=USER_A,
            memory_id=memory.id,
            status=UserMemoryStatusEnum.SUPERSEDED,
        )
        is True
    )


async def test_update_content_cannot_rewrite_another_users_memory(
    repository: UserMemoryRepository,
) -> None:
    memory = await _add(repository, user_id=USER_A, content="original")

    result = await repository.update_content(
        user_id=USER_B,
        memory_id=memory.id,
        kind=UserMemoryKindEnum.FACT,
        content="overwritten",
        content_hash="hash:overwritten",
        embedding=EMBEDDING,
        embedding_model="test-model",
        confidence=1.0,
        last_used_at=NOW,
        expires_at=NOW,
    )

    assert result is None

    await repository.refresh(memory)
    assert memory.content == "original"


async def test_find_active_by_hash_is_scoped_and_ignores_expiry(
    repository: UserMemoryRepository,
) -> None:
    expired = await _add(
        repository,
        user_id=USER_A,
        content="stale fact",
        content_hash="h-stale",
        expires_at=NOW - timedelta(days=1),
    )

    found = await repository.find_active_by_hash(user_id=USER_A, content_hash="h-stale")
    assert found is not None
    assert found.id == expired.id

    assert await repository.find_active_by_hash(user_id=USER_B, content_hash="h-stale") is None


async def test_find_active_by_hash_skips_superseded_rows(
    repository: UserMemoryRepository,
) -> None:
    await _add(
        repository,
        user_id=USER_A,
        content_hash="h-old",
        status=UserMemoryStatusEnum.SUPERSEDED,
    )

    assert await repository.find_active_by_hash(user_id=USER_A, content_hash="h-old") is None


async def test_purge_expired_removes_only_the_callers_expired_rows(
    repository: UserMemoryRepository,
) -> None:
    await _add(repository, user_id=USER_A, content="a expired", expires_at=NOW - timedelta(days=1))
    live = await _add(repository, user_id=USER_A, content="a live")
    other = await _add(
        repository,
        user_id=USER_B,
        content="b expired",
        expires_at=NOW - timedelta(days=1),
    )

    assert await repository.purge_expired(user_id=USER_A, now=NOW) == 1

    assert await repository.get(user_id=USER_A, memory_id=live.id) is not None
    assert await repository.get(user_id=USER_B, memory_id=other.id) is not None


async def test_duplicate_active_content_is_rejected_per_user_but_not_across_users(
    repository: UserMemoryRepository,
) -> None:
    await _add(repository, user_id=USER_A, content_hash="same")

    # A different user may hold an identical fact.
    await _add(repository, user_id=USER_B, content_hash="same")

    # The same user may not hold it twice while both rows are active.
    with pytest.raises(IntegrityError):
        await _add(repository, user_id=USER_A, content="dupe", content_hash="same")
