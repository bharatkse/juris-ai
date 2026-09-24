"""
E2E: user memory tenant isolation, against real Postgres + pgvector.

The property under test is the one the whole feature depends on: user A's
memory must never be visible to user B, *even when it is an exact vector
match for B's query*. Similarity search can't be exercised on the unit
suite's SQLite database (`<=>` is pgvector-only), so this runs the real
repository and service SQL against the real schema.

Every "leak" assertion is set up so that a missing user_id filter would
make it fail: A's row is engineered to be the single best possible match
(identical vector, similarity 1.0) for B's query, so if the filter were
absent it would be returned first.

Requires real Postgres with migrations applied (`make alembic-upgrade`)
and is run via `make test-e2e`. Test users are created with unique ids
and removed afterwards; deleting a user cascades to its memories.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.models.conversation import Conversation
from adapters.persistence.sqlalchemy.models.user import User
from adapters.persistence.sqlalchemy.models.user_memory import UserMemory
from adapters.persistence.sqlalchemy.repositories.compliance_log import (
    ComplianceLogRepository,
)
from adapters.persistence.sqlalchemy.repositories.conversation import (
    ConversationRepository,
)
from adapters.persistence.sqlalchemy.repositories.user import UserRepository
from adapters.persistence.sqlalchemy.repositories.user_memory import (
    UserMemoryRepository,
)
from adapters.persistence.sqlalchemy.session import dispose_engine, session_factory
from application.services.compliance_log import ComplianceLogService
from application.services.user_memory import UserMemoryService, expiry_from
from core.enums import UserMemoryKindEnum, UserMemoryStatusEnum
from rag.models import EmbeddingMetadata

MODEL = "isolation-test-model"
DIMENSION = 384


def _unit_vector(axis: int) -> list[float]:
    vector = [0.0] * DIMENSION
    vector[axis] = 1.0
    return vector


# One embedding, deliberately used by BOTH users' memories and by the query.
SHARED = _unit_vector(0)


class _FixedEmbeddingProvider:
    """Every text embeds to the same vector, so similarity is exact."""

    def __init__(self, vector: list[float]) -> None:
        self._vector = vector
        self.metadata = EmbeddingMetadata(model_name=MODEL, dimension=DIMENSION)

    async def embed(self, *, texts: list[str]) -> list[list[float]]:
        return [self._vector for _ in texts]


@dataclass(frozen=True)
class _Users:
    a: str
    b: str
    # One real conversation each: retrieval fails closed for a
    # conversation that does not exist, so without these a "nothing
    # leaked" assertion could pass for the wrong reason.
    conv_a: str
    conv_b: str


@pytest_asyncio.fixture
async def users() -> AsyncIterator[_Users]:
    # See tests/e2e/conftest.py: the shared engine may hold connections
    # from another test's event loop.
    await dispose_engine()

    tag = uuid.uuid4().hex[:8]
    created: list[User] = []

    async with session_factory() as session:
        for label in ("a", "b"):
            user = User(
                email=f"memory-isolation-{label}-{tag}@example.test",
                password_hash="not-a-real-hash",
                is_active=True,
                memory_enabled=True,
            )
            session.add(user)
            created.append(user)

        await session.flush()

        conversations = [
            Conversation(user_id=user.id, title=f"isolation {label}")
            for label, user in zip(("a", "b"), created, strict=True)
        ]
        session.add_all(conversations)

        await session.commit()

        ids = _Users(
            a=created[0].id,
            b=created[1].id,
            conv_a=conversations[0].id,
            conv_b=conversations[1].id,
        )

    try:
        yield ids
    finally:
        async with session_factory() as session:
            # conversations.user_id has no ON DELETE CASCADE.
            await session.execute(
                delete(Conversation).where(Conversation.id.in_([ids.conv_a, ids.conv_b])),
            )
            await session.execute(delete(User).where(User.id.in_([ids.a, ids.b])))
            await session.commit()

        await dispose_engine()


async def _seed(
    user_id: str,
    *,
    content: str,
    kind: UserMemoryKindEnum = UserMemoryKindEnum.PREFERENCE,
    vector: list[float] | None = None,
    expires_at: datetime | None = None,
) -> str:
    now = datetime.now(UTC)

    async with session_factory() as session:
        memory = await UserMemoryRepository(session=session).add(
            user_id=user_id,
            kind=kind,
            content=content,
            content_hash=hashlib.sha256(f"{user_id}:{content}".encode()).hexdigest(),
            embedding=vector or SHARED,
            embedding_model=MODEL,
            confidence=1.0,
            last_used_at=now,
            expires_at=expires_at or expiry_from(now),
        )
        await session.commit()

        return memory.id


def _service(session: AsyncSession, vector: list[float] | None = None) -> UserMemoryService:
    return UserMemoryService(
        session=session,
        repository=UserMemoryRepository(session=session),
        user_repository=UserRepository(session=session),
        conversation_repository=ConversationRepository(session=session),
        embedding_provider=_FixedEmbeddingProvider(vector or SHARED),
        compliance_log=ComplianceLogService(
            session=session,
            repository=ComplianceLogRepository(session=session),
        ),
    )


async def _search(user_id: str, *, vector: list[float] | None = None, min_similarity: float = -1.0):
    async with session_factory() as session:
        return await UserMemoryRepository(session=session).search_similar(
            user_id=user_id,
            embedding=vector or SHARED,
            embedding_model=MODEL,
            now=datetime.now(UTC),
            limit=100,
            min_similarity=min_similarity,
        )


# ----------------------------------------------------------------------
# The leakage property
# ----------------------------------------------------------------------


async def test_an_exact_vector_match_owned_by_another_user_is_never_returned(
    users: _Users,
) -> None:
    a_id = await _seed(users.a, content="A: client is a hospital group")

    # Sanity: it really is an exact match for A itself, so the assertion
    # below is only meaningful because the row would otherwise rank first.
    a_hits = await _search(users.a)
    assert [(memory.id, round(score, 6)) for memory, score in a_hits] == [(a_id, 1.0)]

    # B has no memories at all. Nothing may come back, however permissive
    # the similarity floor.
    assert await _search(users.b, min_similarity=-1.0) == []


async def test_each_user_only_ever_sees_their_own_rows_when_both_match_exactly(
    users: _Users,
) -> None:
    a_id = await _seed(users.a, content="A's fact")
    b_id = await _seed(users.b, content="B's fact")

    a_hits = await _search(users.a)
    b_hits = await _search(users.b)

    assert {memory.id for memory, _ in a_hits} == {a_id}
    assert {memory.id for memory, _ in b_hits} == {b_id}
    assert all(memory.user_id == users.a for memory, _ in a_hits)
    assert all(memory.user_id == users.b for memory, _ in b_hits)


async def test_service_retrieval_for_one_user_never_includes_another_users_memories(
    users: _Users,
) -> None:
    await _seed(users.a, content="A: matter concerns a merger", kind=UserMemoryKindEnum.FACT)
    await _seed(users.a, content="A: practises in Mumbai", kind=UserMemoryKindEnum.PROFILE)
    b_id = await _seed(users.b, content="B: prefers bullet points")

    async with session_factory() as session:
        b_items = await _service(session).retrieve_for_prompt(
            user_id=users.b, conversation_id=users.conv_b, query="q"
        )

        await session.commit()

    assert [item.id for item in b_items] == [b_id]
    assert all("A:" not in item.content for item in b_items)


async def test_another_users_profile_memory_is_not_injected_by_the_always_include_rule(
    users: _Users,
) -> None:
    # Profile memories bypass the similarity floor, so they are the path
    # most likely to leak if the user filter were missing.
    await _seed(
        users.a, content="A: profile", kind=UserMemoryKindEnum.PROFILE, vector=_unit_vector(5)
    )

    async with session_factory() as session:
        items = await _service(session).retrieve_for_prompt(
            user_id=users.b, conversation_id=users.conv_b, query="q"
        )

        # Positive control: the same call is not vacuously empty -- the
        # owner's own profile memory is returned through it.
        owners = await _service(session).retrieve_for_prompt(
            user_id=users.a, conversation_id=users.conv_a, query="q"
        )

    assert items == ()
    assert [item.content for item in owners] == ["A: profile"]


async def test_a_user_cannot_read_or_delete_another_users_memory_by_id(
    users: _Users,
) -> None:
    a_id = await _seed(users.a, content="A's private fact")

    async with session_factory() as session:
        repository = UserMemoryRepository(session=session)

        assert await repository.get(user_id=users.b, memory_id=a_id) is None
        assert await repository.delete(user_id=users.b, memory_id=a_id) is False
        assert (
            await repository.set_status(
                user_id=users.b,
                memory_id=a_id,
                status=UserMemoryStatusEnum.SUPERSEDED,
            )
            is False
        )

        await session.commit()

    async with session_factory() as session:
        survivor = await UserMemoryRepository(session=session).get(user_id=users.a, memory_id=a_id)

    assert survivor is not None
    assert survivor.status == "active"


# ----------------------------------------------------------------------
# Real pgvector ranking (the only place the `<=>` SQL runs)
# ----------------------------------------------------------------------


async def test_similarity_orders_by_cosine_and_respects_the_floor(
    users: _Users,
) -> None:
    near = await _seed(users.a, content="near", vector=SHARED)

    # 45 degrees from the query: cosine similarity ~0.707.
    diagonal = [0.0] * DIMENSION
    diagonal[0] = diagonal[1] = 2**-0.5
    mid = await _seed(users.a, content="mid", vector=diagonal)

    # Orthogonal to the query: cosine similarity 0.
    far = await _seed(users.a, content="far", vector=_unit_vector(1))

    ranked = await _search(users.a, min_similarity=-1.0)
    assert [memory.id for memory, _ in ranked] == [near, mid, far]

    scores = [score for _, score in ranked]
    assert scores[0] == pytest.approx(1.0, abs=1e-5)
    assert scores[1] == pytest.approx(0.7071, abs=1e-3)
    assert scores[2] == pytest.approx(0.0, abs=1e-5)

    floored = await _search(users.a, min_similarity=0.5)
    assert [memory.id for memory, _ in floored] == [near, mid]


async def test_expired_memories_are_excluded_from_similarity_search(
    users: _Users,
) -> None:
    live = await _seed(users.a, content="live")
    await _seed(users.a, content="expired", expires_at=datetime.now(UTC) - timedelta(seconds=5))

    hits = await _search(users.a)

    assert [memory.id for memory, _ in hits] == [live]


async def test_memories_from_a_different_embedding_model_are_not_compared(
    users: _Users,
) -> None:
    await _seed(users.a, content="same model")

    async with session_factory() as session:
        hits = await UserMemoryRepository(session=session).search_similar(
            user_id=users.a,
            embedding=SHARED,
            embedding_model="some-other-model",
            now=datetime.now(UTC),
            limit=10,
            min_similarity=-1.0,
        )

    assert hits == []


# ----------------------------------------------------------------------
# Consent, on the real database
# ----------------------------------------------------------------------


async def test_no_memory_is_retrieved_for_a_user_who_has_not_consented(
    users: _Users,
) -> None:
    await _seed(users.a, content="stored while consented")

    async with session_factory() as session:
        service = _service(session)

        await service.set_consent(user_id=users.a, enabled=False)

    # Withdrawal already deleted the rows; re-seed one directly to prove
    # the read path itself also refuses without consent, independent of
    # the delete.
    await _seed(users.a, content="inserted behind the service's back")

    async with session_factory() as session:
        items = await _service(session).retrieve_for_prompt(
            user_id=users.a, conversation_id=users.conv_a, query="q"
        )

    assert items == ()


async def test_withdrawing_consent_hard_deletes_only_that_users_memories(
    users: _Users,
) -> None:
    await _seed(users.a, content="a1")
    await _seed(users.a, content="a2")
    b_id = await _seed(users.b, content="b1")

    async with session_factory() as session:
        await _service(session).set_consent(user_id=users.a, enabled=False)

    async with session_factory() as session:
        rows = (
            await session.execute(
                select(UserMemory.id, UserMemory.user_id).where(
                    UserMemory.user_id.in_([users.a, users.b]),
                )
            )
        ).all()

        flag = (
            await session.execute(select(User.memory_enabled).where(User.id == users.a))
        ).scalar_one()

    assert [(row.id, row.user_id) for row in rows] == [(b_id, users.b)]
    assert flag is False


async def test_deleting_a_user_cascades_to_their_memories(
    users: _Users,
) -> None:
    await _seed(users.a, content="goes with the account")
    b_id = await _seed(users.b, content="stays")

    async with session_factory() as session:
        # conversations.user_id has no ON DELETE CASCADE (documented,
        # known gap -- see docs/server/architecture/user-memory.md item
        # 8): a real deletion path must remove conversations first. The
        # `users` fixture gives each user one, so it must go before the
        # user row for this delete to succeed at all.
        await session.execute(delete(Conversation).where(Conversation.id == users.conv_a))
        await session.execute(delete(User).where(User.id == users.a))
        await session.commit()

    async with session_factory() as session:
        rows = (
            await session.execute(
                select(UserMemory.id, UserMemory.user_id).where(
                    UserMemory.user_id.in_([users.a, users.b]),
                )
            )
        ).all()

    # A's memory went with A's account; B's is untouched.
    assert [(row.id, row.user_id) for row in rows] == [(b_id, users.b)]


# ----------------------------------------------------------------------
# Privileges
# ----------------------------------------------------------------------


@pytest.mark.parametrize("privilege", ["SELECT", "INSERT", "UPDATE", "DELETE"])
async def test_runtime_role_has_dml_on_user_memories_without_a_migration_grant(
    users: _Users,
    privilege: str,
) -> None:
    # The migration issues no GRANT; the runtime role must get access
    # from the database's standing ALTER DEFAULT PRIVILEGES, exactly as
    # for every other table. If this fails, the database was created
    # without the role bootstrap -- run scripts/bash/setup_app_role.sh.
    async with session_factory() as session:
        held = (
            await session.execute(
                text("select has_table_privilege(current_user, 'user_memories', :privilege)"),
                {"privilege": privilege},
            )
        ).scalar_one()

    assert held is True
