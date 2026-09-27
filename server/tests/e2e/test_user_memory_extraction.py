"""
E2E: user memory extraction (the write path), against real Postgres.

The LLM is the only fake: a scripted client that records exactly what it
was sent and returns canned operations. Everything else -- the watermark
claim, the consent lock, the guard, the purge, the compliance log -- is
the real code on the real schema.

The interesting cases are the races the design exists to survive:
consent withdrawn while the LLM is running, the per-conversation switch
flipped while it is running, two extractions racing on one conversation.

Requires real Postgres with migrations applied. Run via `make test-e2e`.
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from adapters.persistence.sqlalchemy.models.compliance_log import ComplianceLog
from adapters.persistence.sqlalchemy.models.conversation import Conversation
from adapters.persistence.sqlalchemy.models.conversation_event import ConversationEvent
from adapters.persistence.sqlalchemy.models.user import User
from adapters.persistence.sqlalchemy.models.user_memory import UserMemory
from adapters.persistence.sqlalchemy.repositories.conversation import (
    ConversationRepository,
)
from adapters.persistence.sqlalchemy.repositories.user_memory import (
    UserMemoryRepository,
)
from adapters.persistence.sqlalchemy.session import dispose_engine, session_factory
from application.services import user_memory as user_memory_module
from application.services.memory_content_guard import MemoryContentGuard
from application.services.user_memory import expiry_from, hash_content
from application.services.user_memory_extraction import (
    MemoryExtractionSchema,
    MemoryOperationSchema,
    UserMemoryExtractor,
)
from config.settings import get_settings
from core.constants import USER_MEMORY_EXTRACTION_TURN_INTERVAL
from core.enums import ComplianceEventTypeEnum, MessageRoleEnum, UserMemoryKindEnum
from rag.models import EmbeddingMetadata

MODEL = "extraction-test-model"
DIMENSION = 384
VECTOR = [1.0] + [0.0] * (DIMENSION - 1)

ASSISTANT_CANARY = "assistant-said-this-privileged-sentence"


class _FixedEmbeddingProvider:
    def __init__(self) -> None:
        self.metadata = EmbeddingMetadata(model_name=MODEL, dimension=DIMENSION)

    async def embed(self, *, texts: list[str]) -> list[list[float]]:
        return [VECTOR for _ in texts]


class _ScriptedLLM:
    """
    Records every request and returns the scripted operations. ``before``
    runs first, letting a test change the world while the "LLM" is busy.
    """

    def __init__(
        self,
        operations: list[MemoryOperationSchema] | None = None,
        *,
        fail: bool = False,
        before: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self.operations = operations or []
        self.fail = fail
        self.before = before
        self.requests: list = []

    async def generate_structured(self, *, request, response_model):
        self.requests.append(request)

        if self.before is not None:
            await self.before()

        if self.fail:
            raise RuntimeError("provider down")

        return MemoryExtractionSchema(operations=self.operations)


def _no_detections_detector() -> MagicMock:
    detector = MagicMock()
    detector.review.return_value = ("", ())

    return detector


def _extractor(llm: _ScriptedLLM) -> UserMemoryExtractor:
    return UserMemoryExtractor(
        session_factory=session_factory,
        embedding_provider=_FixedEmbeddingProvider(),
        llm_client_factory=lambda: llm,  # type: ignore[arg-type, return-value]
        guard=MemoryContentGuard(pii_detector=_no_detections_detector()),
    )


def _add(content: str, **kwargs) -> MemoryOperationSchema:
    return MemoryOperationSchema(
        op="add",
        kind=UserMemoryKindEnum.PREFERENCE,
        content=content,
        confidence=0.9,
        **kwargs,
    )


@dataclass(frozen=True)
class _World:
    user_id: str
    other_user_id: str
    conversation_id: str


@pytest_asyncio.fixture
async def world() -> AsyncIterator[_World]:
    await dispose_engine()

    tag = uuid.uuid4().hex[:8]

    async with session_factory() as session:
        users = [
            User(
                email=f"extraction-{label}-{tag}@example.test",
                password_hash="not-a-real-hash",
                is_active=True,
                memory_enabled=True,
                memory_consent_updated_at=datetime.now(UTC) - timedelta(days=1),
            )
            for label in ("a", "b")
        ]
        session.add_all(users)
        await session.flush()

        conversation = Conversation(title="t", user_id=users[0].id)
        session.add(conversation)
        await session.commit()

        ids = _World(users[0].id, users[1].id, conversation.id)

    try:
        yield ids
    finally:
        # conversations.user_id has no ON DELETE CASCADE at the database
        # level (only the ORM relationship cascades), so children go first.
        async with session_factory() as session:
            await session.execute(
                delete(ConversationEvent).where(
                    ConversationEvent.conversation_id == ids.conversation_id
                )
            )
            await session.execute(
                delete(Conversation).where(Conversation.id == ids.conversation_id)
            )
            await session.execute(delete(User).where(User.id.in_([ids.user_id, ids.other_user_id])))
            await session.commit()

        await dispose_engine()


async def _add_turns(conversation_id: str, count: int, *, prefix: str = "user message") -> None:
    """USER + ASSISTANT event pairs, oldest first."""

    async with session_factory() as session:
        for index in range(count):
            request_id = uuid.uuid4()

            for role, text in (
                (MessageRoleEnum.USER, f"{prefix} {index}"),
                (MessageRoleEnum.ASSISTANT, f"{ASSISTANT_CANARY} {index}"),
            ):
                session.add(
                    ConversationEvent(
                        conversation_id=conversation_id,
                        request_id=request_id,
                        role=role,
                        content=text,
                    )
                )
                await session.flush()

        await session.commit()


async def _watermark(conversation_id: str) -> datetime | None:
    async with session_factory() as session:
        return (
            await session.execute(
                select(Conversation.memory_extracted_through_created_at).where(
                    Conversation.id == conversation_id
                )
            )
        ).scalar_one()


async def _last_user_event_time(conversation_id: str) -> datetime:
    async with session_factory() as session:
        return (
            await session.execute(
                select(ConversationEvent.created_at)
                .where(
                    ConversationEvent.conversation_id == conversation_id,
                    ConversationEvent.role == MessageRoleEnum.USER,
                )
                .order_by(ConversationEvent.created_at.desc())
                .limit(1)
            )
        ).scalar_one()


async def _contents(user_id: str) -> list[str]:
    async with session_factory() as session:
        rows = await session.execute(
            select(UserMemory.content)
            .where(UserMemory.user_id == user_id)
            .order_by(UserMemory.created_at)
        )

        return list(rows.scalars().all())


async def _seed_memory(user_id: str, content: str, *, expires_at: datetime | None = None) -> str:
    now = datetime.now(UTC)

    async with session_factory() as session:
        memory = await UserMemoryRepository(session=session).add(
            user_id=user_id,
            kind=UserMemoryKindEnum.PREFERENCE,
            content=content,
            content_hash=hash_content(content),
            embedding=VECTOR,
            embedding_model=MODEL,
            confidence=1.0,
            last_used_at=now,
            expires_at=expires_at or expiry_from(now),
        )
        await session.commit()

        return memory.id


async def _set(model, where_id: str, **values) -> None:
    async with session_factory() as session:
        await session.execute(update(model).where(model.id == where_id).values(**values))
        await session.commit()


TURNS = USER_MEMORY_EXTRACTION_TURN_INTERVAL


# ----------------------------------------------------------------------
# Happy path and what the model is (not) shown
# ----------------------------------------------------------------------


async def test_extraction_saves_facts_advances_the_watermark_and_audits(world: _World) -> None:
    await _add_turns(world.conversation_id, TURNS)
    llm = _ScriptedLLM([_add("Prefers concise answers"), _add("Practises in Mumbai")])

    outcome = await _extractor(llm).run(
        user_id=world.user_id, conversation_id=world.conversation_id
    )

    assert outcome.status == "extracted"
    assert outcome.applied == 2
    assert sorted(await _contents(world.user_id)) == [
        "Practises in Mumbai",
        "Prefers concise answers",
    ]
    assert await _watermark(world.conversation_id) == await _last_user_event_time(
        world.conversation_id
    )

    async with session_factory() as session:
        rows = (
            (
                await session.execute(
                    select(ComplianceLog).where(
                        ComplianceLog.user_id == world.user_id,
                        ComplianceLog.event_type == ComplianceEventTypeEnum.MEMORY_OPERATION,
                    )
                )
            )
            .scalars()
            .all()
        )

    assert sorted(row.payload["operation"] for row in rows) == ["stored", "stored"]
    assert all(row.conversation_id == world.conversation_id for row in rows)
    assert "Mumbai" not in str([row.payload for row in rows])


async def test_the_model_is_shown_only_user_messages_never_assistant_output(world: _World) -> None:
    await _add_turns(world.conversation_id, TURNS)
    llm = _ScriptedLLM()

    await _extractor(llm).run(user_id=world.user_id, conversation_id=world.conversation_id)

    (request,) = llm.requests
    sent = "\n".join(message.content for message in request.messages)

    assert "user message 0" in sent
    assert ASSISTANT_CANARY not in sent


async def test_an_empty_answer_still_advances_the_watermark(world: _World) -> None:
    await _add_turns(world.conversation_id, TURNS)

    outcome = await _extractor(_ScriptedLLM([])).run(
        user_id=world.user_id, conversation_id=world.conversation_id
    )

    assert outcome.status == "extracted" and outcome.applied == 0
    assert await _watermark(world.conversation_id) is not None


# ----------------------------------------------------------------------
# Cadence
# ----------------------------------------------------------------------


async def test_below_the_turn_interval_nothing_is_sent_to_the_model(world: _World) -> None:
    await _add_turns(world.conversation_id, TURNS - 1)
    llm = _ScriptedLLM([_add("x")])

    outcome = await _extractor(llm).run(
        user_id=world.user_id, conversation_id=world.conversation_id
    )

    assert outcome.status == "skipped_not_enough_turns"
    assert llm.requests == []
    assert await _watermark(world.conversation_id) is None


async def test_the_second_pass_only_considers_messages_after_the_watermark(world: _World) -> None:
    await _add_turns(world.conversation_id, TURNS, prefix="first batch")
    await _extractor(_ScriptedLLM()).run(
        user_id=world.user_id, conversation_id=world.conversation_id
    )

    # Nothing new: skipped.
    idle = _ScriptedLLM()
    assert (
        await _extractor(idle).run(user_id=world.user_id, conversation_id=world.conversation_id)
    ).status == "skipped_not_enough_turns"
    assert idle.requests == []

    await _add_turns(world.conversation_id, TURNS, prefix="second batch")
    second = _ScriptedLLM()
    await _extractor(second).run(user_id=world.user_id, conversation_id=world.conversation_id)

    sent = "\n".join(message.content for message in second.requests[0].messages)
    assert "second batch 0" in sent
    assert "first batch" not in sent


# ----------------------------------------------------------------------
# Consent and the per-conversation switch
# ----------------------------------------------------------------------


async def test_no_consent_means_no_llm_call_and_nothing_stored(world: _World) -> None:
    await _add_turns(world.conversation_id, TURNS)
    await _set(User, world.user_id, memory_enabled=False)
    llm = _ScriptedLLM([_add("x")])

    outcome = await _extractor(llm).run(
        user_id=world.user_id, conversation_id=world.conversation_id
    )

    assert outcome.status == "skipped_no_consent"
    assert llm.requests == [] and await _contents(world.user_id) == []


async def test_the_conversation_switch_stops_extraction(world: _World) -> None:
    await _add_turns(world.conversation_id, TURNS)
    await _set(Conversation, world.conversation_id, memory_disabled=True)
    llm = _ScriptedLLM([_add("x")])

    outcome = await _extractor(llm).run(
        user_id=world.user_id, conversation_id=world.conversation_id
    )

    assert outcome.status == "skipped_conversation_switch_off"
    assert llm.requests == [] and await _contents(world.user_id) == []


async def test_messages_sent_before_consent_was_granted_are_never_read(world: _World) -> None:
    await _add_turns(world.conversation_id, TURNS, prefix="before consent")
    # Consent is (re)granted AFTER those messages.
    await _set(
        User, world.user_id, memory_consent_updated_at=datetime.now(UTC) + timedelta(seconds=1)
    )
    llm = _ScriptedLLM([_add("x")])

    outcome = await _extractor(llm).run(
        user_id=world.user_id, conversation_id=world.conversation_id
    )

    assert outcome.status == "skipped_not_enough_turns"
    assert llm.requests == []


async def test_a_user_can_only_extract_from_their_own_conversation(world: _World) -> None:
    await _add_turns(world.conversation_id, TURNS)
    llm = _ScriptedLLM([_add("x")])

    outcome = await _extractor(llm).run(
        user_id=world.other_user_id, conversation_id=world.conversation_id
    )

    assert outcome.status == "skipped_conversation_unavailable"
    assert llm.requests == []
    assert await _contents(world.other_user_id) == []


async def test_consent_withdrawn_while_the_llm_is_running_writes_nothing(world: _World) -> None:
    await _add_turns(world.conversation_id, TURNS)

    async def withdraw_consent() -> None:
        await _set(User, world.user_id, memory_enabled=False)

    llm = _ScriptedLLM([_add("Prefers concise answers")], before=withdraw_consent)

    outcome = await _extractor(llm).run(
        user_id=world.user_id, conversation_id=world.conversation_id
    )

    assert outcome.status == "skipped_no_consent"
    assert await _contents(world.user_id) == []
    assert await _watermark(world.conversation_id) is None


async def test_the_switch_flipped_while_the_llm_is_running_writes_nothing(world: _World) -> None:
    await _add_turns(world.conversation_id, TURNS)

    async def switch_on() -> None:
        await _set(Conversation, world.conversation_id, memory_disabled=True)

    llm = _ScriptedLLM([_add("Prefers concise answers")], before=switch_on)

    outcome = await _extractor(llm).run(
        user_id=world.user_id, conversation_id=world.conversation_id
    )

    assert outcome.status == "skipped_claim_lost"
    assert await _contents(world.user_id) == []


async def test_two_racing_extractions_apply_exactly_once(world: _World) -> None:
    await _add_turns(world.conversation_id, TURNS)
    both_reached_llm = asyncio.Event()
    arrivals = 0

    async def rendezvous() -> None:
        nonlocal arrivals
        arrivals += 1
        if arrivals == 2:
            both_reached_llm.set()
        await both_reached_llm.wait()

    def racer() -> _ScriptedLLM:
        return _ScriptedLLM([_add("Prefers concise answers")], before=rendezvous)

    first, second = await asyncio.gather(
        _extractor(racer()).run(user_id=world.user_id, conversation_id=world.conversation_id),
        _extractor(racer()).run(user_id=world.user_id, conversation_id=world.conversation_id),
    )

    assert sorted([first.status, second.status]) == ["extracted", "skipped_claim_lost"]
    assert await _contents(world.user_id) == ["Prefers concise answers"]


async def test_two_racing_extractions_from_independent_engines_apply_exactly_once(
    world: _World,
) -> None:
    """
    The previous test races two asyncio tasks sharing this process's
    session_factory (i.e. its one connection pool). This one removes
    even that much sharing: each side gets its own AsyncEngine/
    async_sessionmaker, built fresh against the same database URL --
    the same relationship two separate app-worker processes would have
    to each other and to Postgres (each with its own pool, no shared
    Python state). Nothing here is process-local: the claim
    (application/services/user_memory_extraction.py's write phase --
    SELECT ... FOR SHARE on the consent row, then a single conditional
    UPDATE on the watermark) is a plain SQL statement whose atomicity
    is enforced by Postgres's own row locking and MVCC, not by
    anything in this process (the scheduler's in-flight set is a
    same-process de-dup optimization only, irrelevant to correctness
    here and bypassed entirely by calling the extractor directly).
    If this still applies exactly once, worker count cannot break the
    claim.
    """

    await _add_turns(world.conversation_id, TURNS)

    settings = get_settings()
    worker_a_engine = create_async_engine(settings.async_database_url)
    worker_b_engine = create_async_engine(settings.async_database_url)
    worker_a_sessions = async_sessionmaker(
        bind=worker_a_engine, class_=AsyncSession, expire_on_commit=False
    )
    worker_b_sessions = async_sessionmaker(
        bind=worker_b_engine, class_=AsyncSession, expire_on_commit=False
    )

    both_reached_llm = asyncio.Event()
    arrivals = 0

    async def rendezvous() -> None:
        nonlocal arrivals
        arrivals += 1
        if arrivals == 2:
            both_reached_llm.set()
        await both_reached_llm.wait()

    def racer() -> _ScriptedLLM:
        return _ScriptedLLM([_add("Prefers concise answers")], before=rendezvous)

    def extractor(sessions) -> UserMemoryExtractor:
        return UserMemoryExtractor(
            session_factory=sessions,
            embedding_provider=_FixedEmbeddingProvider(),
            llm_client_factory=lambda: racer(),
            guard=MemoryContentGuard(pii_detector=_no_detections_detector()),
        )

    try:
        first, second = await asyncio.gather(
            extractor(worker_a_sessions).run(
                user_id=world.user_id, conversation_id=world.conversation_id
            ),
            extractor(worker_b_sessions).run(
                user_id=world.user_id, conversation_id=world.conversation_id
            ),
        )
    finally:
        await worker_a_engine.dispose()
        await worker_b_engine.dispose()

    assert sorted([first.status, second.status]) == ["extracted", "skipped_claim_lost"]
    assert await _contents(world.user_id) == ["Prefers concise answers"]


async def test_cancelling_the_write_phase_between_claim_and_commit_persists_nothing(
    world: _World,
) -> None:
    """
    Directly answers whether the watermark claim and the write it
    guards are atomic under cancellation: MemoryExtractionScheduler.
    shutdown() cancels a run that does not finish within its timeout,
    and the claim (ConversationRepository.claim_memory_extraction) and
    every applied operation plus the final commit all run in the SAME
    session/transaction in _write_phase, with no intermediate commit
    between them -- so cancelling anywhere before that commit discards
    the whole transaction, claim included, via the implicit rollback
    AsyncSession performs when its "async with" block exits through an
    exception (CancelledError included; it is not caught by the
    "except SQLAlchemyError" inside _write_phase, so it propagates
    straight out to that exit).

    Proven here, not just argued: the real claim_memory_extraction is
    wrapped to pause AFTER its UPDATE has executed (claimed, uncommitted)
    but BEFORE _write_phase's code even inspects the result -- strictly
    inside the window the concern names. The task is cancelled there.
    """

    await _add_turns(world.conversation_id, TURNS)

    reached_between_claim_and_commit = asyncio.Event()
    real_claim = ConversationRepository.claim_memory_extraction

    async def paused_claim(self, **kwargs):
        claimed = await real_claim(self, **kwargs)
        reached_between_claim_and_commit.set()
        # Suspended here, forever -- the task is cancelled from outside
        # while parked at this await, i.e. after the claim UPDATE ran
        # (uncommitted) and before _write_phase does anything else.
        await asyncio.Event().wait()
        return claimed

    llm = _ScriptedLLM([_add("Prefers concise answers")])

    with patch.object(ConversationRepository, "claim_memory_extraction", paused_claim):
        task = asyncio.create_task(
            _extractor(llm).run(user_id=world.user_id, conversation_id=world.conversation_id)
        )
        await reached_between_claim_and_commit.wait()
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

    # Nothing persisted -- not the watermark, not the content.
    assert await _watermark(world.conversation_id) is None
    assert await _contents(world.user_id) == []

    # And the batch is simply retried cleanly on a later run, exactly as
    # an LLM failure is (see the next test) -- nothing was lost.
    retry = await _extractor(_ScriptedLLM([_add("Prefers concise answers")])).run(
        user_id=world.user_id, conversation_id=world.conversation_id
    )
    assert retry.status == "extracted"
    assert await _contents(world.user_id) == ["Prefers concise answers"]


async def test_an_llm_failure_leaves_the_watermark_so_the_batch_is_retried(world: _World) -> None:
    await _add_turns(world.conversation_id, TURNS)

    outcome = await _extractor(_ScriptedLLM(fail=True)).run(
        user_id=world.user_id, conversation_id=world.conversation_id
    )

    assert outcome.status == "llm_failed"
    assert await _watermark(world.conversation_id) is None

    retry = await _extractor(_ScriptedLLM([_add("Prefers concise answers")])).run(
        user_id=world.user_id, conversation_id=world.conversation_id
    )
    assert retry.status == "extracted"
    assert await _contents(world.user_id) == ["Prefers concise answers"]


# ----------------------------------------------------------------------
# Guard, and what a model may touch
# ----------------------------------------------------------------------


async def test_identifiers_are_blocked_while_the_rest_of_the_batch_is_kept(world: _World) -> None:
    await _add_turns(world.conversation_id, TURNS)
    llm = _ScriptedLLM(
        [
            _add("Their PAN is ABCDE1234F"),
            _add("Aadhaar 2345 6789 0123"),
            _add("Prefers concise answers"),
        ]
    )

    outcome = await _extractor(llm).run(
        user_id=world.user_id, conversation_id=world.conversation_id
    )

    assert await _contents(world.user_id) == ["Prefers concise answers"]
    assert outcome.applied == 1
    # A 12-digit Aadhaar also matches the generic account/card-number
    # pattern, so it is rejected for both reasons.
    assert outcome.rejected == {
        "guard:pan": 1,
        "guard:aadhaar": 1,
        "guard:account_or_card_number": 1,
    }


async def test_a_model_cannot_update_or_delete_another_users_memory(world: _World) -> None:
    await _add_turns(world.conversation_id, TURNS)
    theirs = await _seed_memory(world.other_user_id, "Their private preference")
    llm = _ScriptedLLM(
        [
            MemoryOperationSchema(
                op="update",
                target_id=theirs,
                kind=UserMemoryKindEnum.FACT,
                content="overwritten",
                confidence=0.9,
            ),
            MemoryOperationSchema(op="delete", target_id=theirs, confidence=0.9),
        ]
    )

    outcome = await _extractor(llm).run(
        user_id=world.user_id, conversation_id=world.conversation_id
    )

    assert outcome.rejected == {"unknown_target": 2}
    assert await _contents(world.other_user_id) == ["Their private preference"]


async def test_a_model_can_update_and_delete_memories_it_was_shown(world: _World) -> None:
    await _add_turns(world.conversation_id, TURNS)
    old = await _seed_memory(world.user_id, "Prefers long answers")
    gone = await _seed_memory(world.user_id, "Prefers formal tone")
    llm = _ScriptedLLM(
        [
            MemoryOperationSchema(
                op="update",
                target_id=old,
                kind=UserMemoryKindEnum.PREFERENCE,
                content="Prefers concise answers",
                confidence=0.9,
            ),
            MemoryOperationSchema(op="delete", target_id=gone, confidence=0.9),
        ]
    )

    outcome = await _extractor(llm).run(
        user_id=world.user_id, conversation_id=world.conversation_id
    )

    assert outcome.applied == 2
    assert await _contents(world.user_id) == ["Prefers concise answers"]

    sent = "\n".join(message.content for message in llm.requests[0].messages)
    assert old in sent and gone in sent


# ----------------------------------------------------------------------
# Expiry and the cap
# ----------------------------------------------------------------------


async def test_expired_memories_are_purged_before_extraction_and_not_shown_to_the_model(
    world: _World,
) -> None:
    await _add_turns(world.conversation_id, TURNS)
    expired = await _seed_memory(
        world.user_id, "stale preference", expires_at=datetime.now(UTC) - timedelta(days=1)
    )
    llm = _ScriptedLLM()

    await _extractor(llm).run(user_id=world.user_id, conversation_id=world.conversation_id)

    assert await _contents(world.user_id) == []
    sent = "\n".join(message.content for message in llm.requests[0].messages)
    assert expired not in sent and "stale preference" not in sent


async def test_expired_rows_do_not_count_toward_the_cap(
    world: _World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(user_memory_module, "USER_MEMORY_MAX_PER_USER", 1)
    await _add_turns(world.conversation_id, TURNS)
    await _seed_memory(world.user_id, "stale", expires_at=datetime.now(UTC) - timedelta(days=1))

    outcome = await _extractor(_ScriptedLLM([_add("Prefers concise answers")])).run(
        user_id=world.user_id, conversation_id=world.conversation_id
    )

    assert outcome.applied == 1
    assert await _contents(world.user_id) == ["Prefers concise answers"]


async def test_at_the_cap_a_new_fact_is_skipped_not_fatal(
    world: _World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(user_memory_module, "USER_MEMORY_MAX_PER_USER", 1)
    await _add_turns(world.conversation_id, TURNS)
    await _seed_memory(world.user_id, "already saved")

    outcome = await _extractor(_ScriptedLLM([_add("one too many")])).run(
        user_id=world.user_id, conversation_id=world.conversation_id
    )

    assert outcome.applied == 0
    assert outcome.rejected == {"UserMemoryLimitExceededError": 1}
    assert await _contents(world.user_id) == ["already saved"]
    # The batch still counts as processed.
    assert await _watermark(world.conversation_id) is not None


async def test_re_saving_an_existing_fact_does_not_duplicate_it(world: _World) -> None:
    await _add_turns(world.conversation_id, TURNS)
    await _seed_memory(world.user_id, "Prefers concise answers")

    await _extractor(_ScriptedLLM([_add("prefers   CONCISE answers")])).run(
        user_id=world.user_id, conversation_id=world.conversation_id
    )

    assert await _contents(world.user_id) == ["Prefers concise answers"]


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
