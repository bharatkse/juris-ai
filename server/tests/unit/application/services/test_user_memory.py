"""
Unit tests for UserMemoryService.

The repository and embedding provider are mocked: similarity SQL is
pgvector-only and is exercised against real Postgres in
tests/e2e/test_user_memory_isolation.py. What is pinned down here is the
service's own logic -- consent semantics, dedupe, and how the read path
selects and caps what gets injected into a prompt.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from adapters.persistence.sqlalchemy.models.user_memory import UserMemory
from application.services import user_memory as user_memory_module
from application.services.user_memory import (
    UserMemoryService,
    expiry_from,
    hash_content,
    normalize_content,
)
from core.constants import (
    USER_MEMORY_MAX_CONTENT_CHARS,
    USER_MEMORY_MAX_PER_USER,
    USER_MEMORY_RETENTION_DAYS,
    USER_MEMORY_RETRIEVAL_TOP_K,
)
from core.enums import (
    ActorTypeEnum,
    UserMemoryKindEnum,
    UserMemoryOperationEnum,
    UserMemoryStatusEnum,
)
from core.exceptions.database import DatabaseError
from core.exceptions.httpx import NotFoundError, UserNotFoundError
from core.exceptions.user_memory import (
    InvalidUserMemoryContentError,
    UserMemoryLimitExceededError,
)
from rag.models import EmbeddingMetadata

USER = "user_a"
CONVERSATION = "conv_a"
MODEL = "test-model"


class _Savepoint:
    """Stand-in for AsyncSession.begin_nested()'s async context manager."""

    async def __aenter__(self) -> _Savepoint:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None


def _memory(
    memory_id: str,
    *,
    kind: UserMemoryKindEnum = UserMemoryKindEnum.PREFERENCE,
    content: str = "prefers concise answers",
    status: UserMemoryStatusEnum = UserMemoryStatusEnum.ACTIVE,
    last_used_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> UserMemory:
    return UserMemory(
        id=memory_id,
        user_id=USER,
        kind=kind.value,
        content=content,
        content_hash=hash_content(content),
        embedding=[0.0] * 384,
        embedding_model=MODEL,
        confidence=1.0,
        status=status.value,
        last_used_at=last_used_at or datetime.now(UTC),
        expires_at=expires_at if expires_at is not None else expiry_from(datetime.now(UTC)),
    )


@pytest.fixture
def session() -> MagicMock:
    mock = MagicMock()
    mock.commit = AsyncMock()
    mock.rollback = AsyncMock()
    mock.refresh = AsyncMock()
    mock.begin_nested = MagicMock(side_effect=lambda: _Savepoint())
    return mock


@pytest.fixture
def repository() -> MagicMock:
    mock = MagicMock()
    mock.find_active_by_hash = AsyncMock(return_value=None)
    mock.count_visible = AsyncMock(return_value=0)
    mock.add = AsyncMock(
        side_effect=lambda **kwargs: _memory("umem_new", content=kwargs["content"])
    )
    mock.touch = AsyncMock(return_value=1)
    mock.delete = AsyncMock(return_value=True)
    mock.delete_all = AsyncMock(return_value=3)
    mock.get = AsyncMock(return_value=None)
    mock.list_live_by_kind = AsyncMock(return_value=[])
    mock.search_similar = AsyncMock(return_value=[])
    mock.update_content = AsyncMock(return_value=None)
    mock.set_status = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def user() -> SimpleNamespace:
    return SimpleNamespace(memory_enabled=True, memory_consent_updated_at=None)


@pytest.fixture
def user_repository(user: SimpleNamespace) -> MagicMock:
    mock = MagicMock()
    mock.get = AsyncMock(return_value=user)
    return mock


@pytest.fixture
def conversation_repository() -> MagicMock:
    mock = MagicMock()
    # The "don't remember this" switch is off by default.
    mock.get_memory_disabled = AsyncMock(return_value=False)
    return mock


@pytest.fixture
def embedding_provider() -> MagicMock:
    mock = MagicMock()
    mock.metadata = EmbeddingMetadata(model_name=MODEL, dimension=384)
    mock.embed = AsyncMock(return_value=[[0.1] * 384])
    return mock


@pytest.fixture
def compliance_log() -> MagicMock:
    mock = MagicMock()
    mock.record_memory_operation = AsyncMock()
    return mock


@pytest.fixture
def service(
    session: MagicMock,
    repository: MagicMock,
    user_repository: MagicMock,
    conversation_repository: MagicMock,
    embedding_provider: MagicMock,
    compliance_log: MagicMock,
) -> UserMemoryService:
    return UserMemoryService(
        session=session,
        repository=repository,
        user_repository=user_repository,
        conversation_repository=conversation_repository,
        embedding_provider=embedding_provider,
        compliance_log=compliance_log,
    )


# ----------------------------------------------------------------------
# Content helpers
# ----------------------------------------------------------------------


def test_hash_ignores_case_and_whitespace_but_not_meaning() -> None:
    assert hash_content("Prefers   concise\nanswers") == hash_content("prefers concise answers")
    assert hash_content("prefers concise answers") != hash_content("prefers detailed answers")


def test_normalize_collapses_whitespace() -> None:
    assert normalize_content("  a \n\t b  ") == "a b"


def test_expiry_is_the_single_retention_constant_after_the_moment() -> None:
    moment = datetime(2026, 1, 1, tzinfo=UTC)

    assert expiry_from(moment) == moment + timedelta(days=USER_MEMORY_RETENTION_DAYS)


# ----------------------------------------------------------------------
# Consent
# ----------------------------------------------------------------------


async def test_withdrawing_consent_hard_deletes_everything_in_one_transaction(
    service: UserMemoryService,
    repository: MagicMock,
    session: MagicMock,
    user: SimpleNamespace,
) -> None:
    await service.set_consent(user_id=USER, enabled=False)

    assert user.memory_enabled is False
    assert user.memory_consent_updated_at is not None
    repository.delete_all.assert_awaited_once_with(user_id=USER)
    session.commit.assert_awaited_once()


async def test_granting_consent_does_not_delete_anything(
    service: UserMemoryService,
    repository: MagicMock,
    session: MagicMock,
    user: SimpleNamespace,
) -> None:
    user.memory_enabled = False

    await service.set_consent(user_id=USER, enabled=True)

    assert user.memory_enabled is True
    assert user.memory_consent_updated_at is not None
    repository.delete_all.assert_not_awaited()
    session.commit.assert_awaited_once()


async def test_setting_the_current_consent_value_is_a_noop(
    service: UserMemoryService,
    repository: MagicMock,
    session: MagicMock,
) -> None:
    await service.set_consent(user_id=USER, enabled=True)

    repository.delete_all.assert_not_awaited()
    session.commit.assert_not_awaited()


async def test_consent_for_unknown_user_raises(
    service: UserMemoryService,
    user_repository: MagicMock,
) -> None:
    user_repository.get.return_value = None

    with pytest.raises(UserNotFoundError):
        await service.set_consent(user_id="user_ghost", enabled=True)


async def test_failed_withdrawal_rolls_back_and_surfaces_a_database_error(
    service: UserMemoryService,
    repository: MagicMock,
    session: MagicMock,
) -> None:
    repository.delete_all.side_effect = SQLAlchemyError("boom")

    with pytest.raises(DatabaseError):
        await service.set_consent(user_id=USER, enabled=False)

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


# ----------------------------------------------------------------------
# remember()
# ----------------------------------------------------------------------


async def test_remember_stores_normalized_content_with_its_hash_and_model(
    service: UserMemoryService,
    repository: MagicMock,
) -> None:
    await service.remember(
        user_id=USER,
        kind=UserMemoryKindEnum.PREFERENCE,
        content="  Prefers   concise answers ",
    )

    kwargs = repository.add.await_args.kwargs

    assert kwargs["user_id"] == USER
    assert kwargs["content"] == "Prefers concise answers"
    assert kwargs["content_hash"] == hash_content("prefers concise answers")
    assert kwargs["embedding_model"] == MODEL
    assert kwargs["expires_at"] > kwargs["last_used_at"]


async def test_remember_refreshes_an_existing_identical_fact_instead_of_duplicating(
    service: UserMemoryService,
    repository: MagicMock,
) -> None:
    existing = _memory("umem_1")
    repository.find_active_by_hash.return_value = existing

    result = await service.remember(
        user_id=USER,
        kind=UserMemoryKindEnum.PREFERENCE,
        content="prefers concise answers",
    )

    assert result is existing
    repository.add.assert_not_awaited()
    repository.touch.assert_awaited_once()
    assert repository.touch.await_args.kwargs["memory_ids"] == ["umem_1"]


@pytest.mark.parametrize("content", ["", "   \n  "])
async def test_remember_rejects_empty_content(
    service: UserMemoryService,
    content: str,
) -> None:
    with pytest.raises(InvalidUserMemoryContentError):
        await service.remember(user_id=USER, kind=UserMemoryKindEnum.FACT, content=content)


async def test_remember_rejects_content_longer_than_one_atomic_fact(
    service: UserMemoryService,
    repository: MagicMock,
) -> None:
    with pytest.raises(InvalidUserMemoryContentError):
        await service.remember(
            user_id=USER,
            kind=UserMemoryKindEnum.FACT,
            content="x" * (USER_MEMORY_MAX_CONTENT_CHARS + 1),
        )

    repository.add.assert_not_awaited()


async def test_remember_refuses_past_the_per_user_cap(
    service: UserMemoryService,
    repository: MagicMock,
) -> None:
    repository.count_visible.return_value = USER_MEMORY_MAX_PER_USER

    with pytest.raises(UserMemoryLimitExceededError):
        await service.remember(user_id=USER, kind=UserMemoryKindEnum.FACT, content="one more")

    repository.add.assert_not_awaited()


# ----------------------------------------------------------------------
# Self-service
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "row",
    [
        None,
        _memory("umem_x", status=UserMemoryStatusEnum.SUPERSEDED),
        _memory("umem_x", expires_at=datetime.now(UTC) - timedelta(days=1)),
    ],
    ids=["missing-or-other-users", "superseded", "expired"],
)
async def test_get_memory_hides_rows_the_user_should_not_see(
    service: UserMemoryService,
    repository: MagicMock,
    row: UserMemory | None,
) -> None:
    repository.get.return_value = row

    with pytest.raises(NotFoundError):
        await service.get_memory(user_id=USER, memory_id="umem_x")


async def test_get_memory_returns_a_visible_row(
    service: UserMemoryService,
    repository: MagicMock,
) -> None:
    row = _memory("umem_1")
    repository.get.return_value = row

    assert await service.get_memory(user_id=USER, memory_id="umem_1") is row


async def test_delete_memory_commits_and_reports_missing_ids_as_not_found(
    service: UserMemoryService,
    repository: MagicMock,
    session: MagicMock,
) -> None:
    repository.get.return_value = _memory("umem_1")

    await service.delete_memory(user_id=USER, memory_id="umem_1")

    repository.delete.assert_awaited_once_with(user_id=USER, memory_id="umem_1")
    session.commit.assert_awaited_once()

    repository.get.return_value = None

    with pytest.raises(NotFoundError):
        await service.delete_memory(user_id=USER, memory_id="umem_missing")


# ----------------------------------------------------------------------
# is_enabled_for_conversation() -- the switch suppresses INJECTION too
# ----------------------------------------------------------------------


async def test_conversation_switch_off_and_consent_on_is_enabled(
    service: UserMemoryService,
    conversation_repository: MagicMock,
) -> None:
    conversation_repository.get_memory_disabled.return_value = False

    assert await service.is_enabled_for_conversation(user_id=USER, conversation_id=CONVERSATION)


async def test_conversation_switch_on_disables_even_with_consent(
    service: UserMemoryService,
    conversation_repository: MagicMock,
) -> None:
    conversation_repository.get_memory_disabled.return_value = True

    assert not await service.is_enabled_for_conversation(user_id=USER, conversation_id=CONVERSATION)


async def test_no_consent_disables_without_even_checking_the_conversation(
    service: UserMemoryService,
    conversation_repository: MagicMock,
    user: SimpleNamespace,
) -> None:
    user.memory_enabled = False

    assert not await service.is_enabled_for_conversation(user_id=USER, conversation_id=CONVERSATION)
    conversation_repository.get_memory_disabled.assert_not_awaited()


async def test_a_conversation_that_does_not_exist_for_this_user_fails_closed(
    service: UserMemoryService,
    conversation_repository: MagicMock,
) -> None:
    # No such (non-archived) conversation for this user -> None.
    conversation_repository.get_memory_disabled.return_value = None

    assert not await service.is_enabled_for_conversation(user_id=USER, conversation_id=CONVERSATION)


async def test_retrieval_returns_nothing_when_the_conversation_switch_is_on(
    service: UserMemoryService,
    repository: MagicMock,
    embedding_provider: MagicMock,
    conversation_repository: MagicMock,
) -> None:
    conversation_repository.get_memory_disabled.return_value = True
    repository.list_live_by_kind.return_value = [
        _memory("umem_p1", kind=UserMemoryKindEnum.PROFILE, content="would otherwise match"),
    ]

    items = await service.retrieve_for_prompt(user_id=USER, conversation_id=CONVERSATION, query="q")

    assert items == ()
    repository.search_similar.assert_not_awaited()
    repository.list_live_by_kind.assert_not_awaited()
    embedding_provider.embed.assert_not_awaited()


# ----------------------------------------------------------------------
# retrieve_for_prompt()
# ----------------------------------------------------------------------


async def test_retrieval_returns_nothing_and_skips_search_without_consent(
    service: UserMemoryService,
    repository: MagicMock,
    embedding_provider: MagicMock,
    user: SimpleNamespace,
) -> None:
    user.memory_enabled = False

    assert (
        await service.retrieve_for_prompt(
            user_id=USER, conversation_id=CONVERSATION, query="anything"
        )
        == ()
    )

    repository.search_similar.assert_not_awaited()
    repository.list_live_by_kind.assert_not_awaited()
    embedding_provider.embed.assert_not_awaited()


async def test_retrieval_ignores_a_blank_query(
    service: UserMemoryService,
    repository: MagicMock,
) -> None:
    assert (
        await service.retrieve_for_prompt(user_id=USER, conversation_id=CONVERSATION, query="   ")
        == ()
    )

    repository.search_similar.assert_not_awaited()


async def test_profile_memories_are_always_included_even_with_no_similar_match(
    service: UserMemoryService,
    repository: MagicMock,
) -> None:
    repository.list_live_by_kind.return_value = [
        _memory("umem_p1", kind=UserMemoryKindEnum.PROFILE, content="practices in Delhi"),
    ]
    repository.search_similar.return_value = []

    items = await service.retrieve_for_prompt(
        user_id=USER, conversation_id=CONVERSATION, query="unrelated question"
    )

    assert [item.id for item in items] == ["umem_p1"]
    assert items[0].kind is UserMemoryKindEnum.PROFILE


async def test_retrieval_never_exceeds_top_k_and_does_not_duplicate_profile_hits(
    service: UserMemoryService,
    repository: MagicMock,
) -> None:
    profile = _memory("umem_p1", kind=UserMemoryKindEnum.PROFILE, content="practices in Delhi")
    repository.list_live_by_kind.return_value = [profile]
    repository.search_similar.return_value = [(profile, 0.99)] + [
        (_memory(f"umem_s{index}", content=f"similar {index}"), 0.9 - index * 0.01)
        for index in range(10)
    ]

    items = await service.retrieve_for_prompt(user_id=USER, conversation_id=CONVERSATION, query="q")

    ids = [item.id for item in items]

    assert len(ids) == USER_MEMORY_RETRIEVAL_TOP_K
    assert len(set(ids)) == len(ids)
    assert ids[0] == "umem_p1"


async def test_recency_bonus_breaks_a_near_tie_but_not_a_real_gap(
    service: UserMemoryService,
    repository: MagicMock,
) -> None:
    now = datetime.now(UTC)
    stale = _memory("umem_stale", content="stale", last_used_at=now - timedelta(days=90))
    fresh = _memory("umem_fresh", content="fresh", last_used_at=now)
    far_worse = _memory("umem_far", content="far", last_used_at=now)

    repository.search_similar.return_value = [
        (stale, 0.80),
        (fresh, 0.79),  # within the bonus of stale: recency should win
        (far_worse, 0.60),  # a real gap: recency must not rescue it
    ]

    items = await service.retrieve_for_prompt(user_id=USER, conversation_id=CONVERSATION, query="q")

    assert [item.id for item in items] == ["umem_fresh", "umem_stale", "umem_far"]


async def test_prompt_block_is_cut_by_whole_items_at_the_token_cap(
    service: UserMemoryService,
    repository: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(user_memory_module, "USER_MEMORY_MAX_PROMPT_TOKENS", 25)

    repository.search_similar.return_value = [
        (
            _memory(f"umem_{index}", content="prefers concise structured answers " * 2),
            0.9 - index / 100,
        )
        for index in range(5)
    ]

    items = await service.retrieve_for_prompt(user_id=USER, conversation_id=CONVERSATION, query="q")

    assert 0 < len(items) < 5
    # Never truncated mid-item: every kept item is whole.
    assert all(item.content == "prefers concise structured answers " * 2 for item in items)


async def test_selected_memories_have_their_retention_window_slid_forward(
    service: UserMemoryService,
    repository: MagicMock,
) -> None:
    repository.search_similar.return_value = [
        (_memory("umem_1"), 0.9),
        (_memory("umem_2", content="other"), 0.8),
    ]

    await service.retrieve_for_prompt(user_id=USER, conversation_id=CONVERSATION, query="q")

    kwargs = repository.touch.await_args.kwargs

    assert kwargs["user_id"] == USER
    assert set(kwargs["memory_ids"]) == {"umem_1", "umem_2"}
    assert kwargs["expires_at"] - kwargs["last_used_at"] == timedelta(
        days=USER_MEMORY_RETENTION_DAYS
    )


async def test_retrieval_failure_degrades_to_no_memory_instead_of_breaking_the_request(
    service: UserMemoryService,
    repository: MagicMock,
) -> None:
    repository.search_similar.side_effect = SQLAlchemyError("db down")

    assert (
        await service.retrieve_for_prompt(user_id=USER, conversation_id=CONVERSATION, query="q")
        == ()
    )


async def test_embedding_failure_degrades_to_no_memory(
    service: UserMemoryService,
    embedding_provider: MagicMock,
) -> None:
    embedding_provider.embed.side_effect = RuntimeError("model not loaded")

    assert (
        await service.retrieve_for_prompt(user_id=USER, conversation_id=CONVERSATION, query="q")
        == ()
    )


async def test_retrieval_runs_inside_a_savepoint(
    service: UserMemoryService,
    session: MagicMock,
) -> None:
    await service.retrieve_for_prompt(user_id=USER, conversation_id=CONVERSATION, query="q")

    session.begin_nested.assert_called_once()


# ----------------------------------------------------------------------
# Compliance logging: identifiers, counts and hashes only
# ----------------------------------------------------------------------

_ALLOWED_AUDIT_KEYS = {
    "user_id",
    "tenant_id",
    "operation",
    "actor_type",
    "memory_id",
    "content_hash",
    "kind",
    "count",
    "conversation_id",
    "conversation_event_id",
}

# Distinctive enough that it cannot appear in a payload by coincidence.
CANARY = "the-client-is-acme-holdings-in-a-sealed-arbitration"


def _audits(compliance_log: MagicMock) -> list[dict]:
    return [call.kwargs for call in compliance_log.record_memory_operation.await_args_list]


async def test_consent_withdrawal_is_audited_with_the_deleted_count_in_the_same_commit(
    service: UserMemoryService,
    compliance_log: MagicMock,
    session: MagicMock,
) -> None:
    await service.set_consent(user_id=USER, enabled=False)

    (audit,) = _audits(compliance_log)

    assert audit["operation"] is UserMemoryOperationEnum.CONSENT_WITHDRAWN
    assert audit["actor_type"] is ActorTypeEnum.USER
    assert audit["count"] == 3
    session.commit.assert_awaited_once()


async def test_granting_consent_is_audited_without_a_count(
    service: UserMemoryService,
    compliance_log: MagicMock,
    user: SimpleNamespace,
) -> None:
    user.memory_enabled = False

    await service.set_consent(user_id=USER, enabled=True)

    (audit,) = _audits(compliance_log)

    assert audit["operation"] is UserMemoryOperationEnum.CONSENT_GRANTED
    assert audit["count"] is None


async def test_a_failed_audit_write_rolls_back_the_consent_change(
    service: UserMemoryService,
    compliance_log: MagicMock,
    session: MagicMock,
) -> None:
    compliance_log.record_memory_operation.side_effect = SQLAlchemyError("audit insert failed")

    with pytest.raises(DatabaseError):
        await service.set_consent(user_id=USER, enabled=False)

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


async def test_storing_a_memory_is_audited_with_its_hash_not_its_text(
    service: UserMemoryService,
    compliance_log: MagicMock,
) -> None:
    await service.remember(
        user_id=USER,
        kind=UserMemoryKindEnum.FACT,
        content=CANARY,
        source_conversation_id="conv_1",
    )

    (audit,) = _audits(compliance_log)

    assert audit["operation"] is UserMemoryOperationEnum.STORED
    assert audit["content_hash"] == hash_content(CANARY)
    assert audit["memory_id"] == "umem_new"
    assert audit["conversation_id"] == "conv_1"


async def test_refreshing_an_existing_fact_writes_no_audit_entry(
    service: UserMemoryService,
    repository: MagicMock,
    compliance_log: MagicMock,
) -> None:
    repository.find_active_by_hash.return_value = _memory("umem_1")

    await service.remember(
        user_id=USER,
        kind=UserMemoryKindEnum.PREFERENCE,
        content="prefers concise answers",
    )

    compliance_log.record_memory_operation.assert_not_awaited()


async def test_deleting_a_memory_is_audited_with_the_hash_of_what_was_deleted(
    service: UserMemoryService,
    repository: MagicMock,
    compliance_log: MagicMock,
) -> None:
    repository.get.return_value = _memory("umem_1", content=CANARY)

    await service.delete_memory(user_id=USER, memory_id="umem_1")

    (audit,) = _audits(compliance_log)

    assert audit["operation"] is UserMemoryOperationEnum.DELETED
    assert audit["actor_type"] is ActorTypeEnum.USER
    assert audit["memory_id"] == "umem_1"
    assert audit["content_hash"] == hash_content(CANARY)


async def test_deleting_a_missing_memory_writes_no_audit_entry(
    service: UserMemoryService,
    repository: MagicMock,
    compliance_log: MagicMock,
) -> None:
    repository.get.return_value = None

    with pytest.raises(NotFoundError):
        await service.delete_memory(user_id=USER, memory_id="umem_missing")

    compliance_log.record_memory_operation.assert_not_awaited()


async def test_purging_expired_rows_is_audited_only_when_something_was_purged(
    service: UserMemoryService,
    repository: MagicMock,
    compliance_log: MagicMock,
) -> None:
    repository.purge_expired = AsyncMock(return_value=0)
    await service.purge_expired(user_id=USER)
    compliance_log.record_memory_operation.assert_not_awaited()

    repository.purge_expired.return_value = 4
    await service.purge_expired(user_id=USER)

    (audit,) = _audits(compliance_log)
    assert audit["operation"] is UserMemoryOperationEnum.PURGED_EXPIRED
    assert audit["count"] == 4


async def test_no_operation_ever_puts_memory_text_into_the_audit_log(
    service: UserMemoryService,
    repository: MagicMock,
    compliance_log: MagicMock,
    user: SimpleNamespace,
) -> None:
    repository.get.return_value = _memory("umem_1", content=CANARY)
    repository.update_content.return_value = _memory("umem_1", content=CANARY)
    repository.purge_expired = AsyncMock(return_value=2)

    await service.remember(user_id=USER, kind=UserMemoryKindEnum.FACT, content=CANARY)
    await service.update(
        user_id=USER,
        memory_id="umem_1",
        kind=UserMemoryKindEnum.FACT,
        content=CANARY,
    )
    await service.supersede(user_id=USER, memory_id="umem_1")
    await service.delete_memory(user_id=USER, memory_id="umem_1")
    await service.delete_all(user_id=USER)
    await service.purge_expired(user_id=USER)
    await service.set_consent(user_id=USER, enabled=False)

    audits = _audits(compliance_log)

    assert len(audits) >= 7

    for audit in audits:
        assert set(audit) <= _ALLOWED_AUDIT_KEYS
        assert CANARY not in repr(audit)
        assert "acme" not in repr(audit).lower()
