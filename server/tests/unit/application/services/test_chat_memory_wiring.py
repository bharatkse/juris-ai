"""
Unit tests for how ChatService is wired to user memory.

Write hook: extraction is scheduled only AFTER the turn commits, never
when the turn fails, never for a conversation whose "don't remember this"
switch is on.

Read path: the memories selected for a turn travel ChatService ->
OrchestratorRequest -> ConversationDTO -> the agent prompt, as their own
system block. The switch test at the bottom builds the real prompt from
a real UserMemoryService (only its repositories are faked) to prove that
with the switch on, a memory that would otherwise match is nowhere in
the messages the model receives.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from agentic.agents.prompts.legal import LegalPromptBuilder
from agentic.orchestration.orchestrator import AIOrchestrator
from agentic.orchestration.schemas.request import OrchestratorRequest
from application.services.chat import ChatService
from application.services.user_memory import UserMemoryService
from core.dto.agent import AgentRequestDTO
from core.dto.user_memory import UserMemoryContextItem
from core.enums import MessageRoleEnum, UserMemoryKindEnum
from core.models.conversation import ConversationMessageSchema
from rag.models import EmbeddingMetadata
from tests.builders.agentic.agent import build_agent_context
from tests.builders.agentic.orchestrator import build_orchestrator_response
from tests.unit.factories.conversation import ConversationFactory
from tests.unit.factories.conversation_event import ConversationEventFactory

SECRET_MEMORY = "Always draft in British English spelling"
MODEL = "unit-test-model"


class _Savepoint:
    """Stand-in for AsyncSession.begin_nested()'s async context manager."""

    async def __aenter__(self) -> _Savepoint:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None


def _item(content: str = SECRET_MEMORY) -> UserMemoryContextItem:
    return UserMemoryContextItem(
        id="umem_" + "a" * 32,
        kind=UserMemoryKindEnum.PREFERENCE,
        content=content,
    )


def _service(
    mock_async_session: AsyncMock,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
    mock_action_workflow_service: MagicMock,
    mock_usage_service: MagicMock,
    mock_conversation_summarization_service: MagicMock,
    mock_compliance_log_service: MagicMock,
    **extra: object,
) -> ChatService:
    return ChatService(
        session=mock_async_session,
        conversation_service=mock_conversation_service,
        conversation_event_service=mock_conversation_event_service,
        orchestrator=mock_orchestrator,
        action_workflow_service=mock_action_workflow_service,
        usage_service=mock_usage_service,
        conversation_summarization_service=mock_conversation_summarization_service,
        compliance_log_service=mock_compliance_log_service,
        **extra,  # type: ignore[arg-type]
    )


# ----------------------------------------------------------------------
# Write hook
# ----------------------------------------------------------------------


@pytest.fixture
def scheduler() -> MagicMock:
    return MagicMock()


@pytest.fixture
def wired(
    mock_async_session: AsyncMock,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
    mock_action_workflow_service: MagicMock,
    mock_usage_service: MagicMock,
    mock_conversation_summarization_service: MagicMock,
    mock_compliance_log_service: MagicMock,
    scheduler: MagicMock,
) -> ChatService:
    return _service(
        mock_async_session,
        mock_conversation_service,
        mock_conversation_event_service,
        mock_orchestrator,
        mock_action_workflow_service,
        mock_usage_service,
        mock_conversation_summarization_service,
        mock_compliance_log_service,
        memory_extraction_scheduler=scheduler,
    )


def _prime_chat(
    conversation: SimpleNamespace | object,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    request_id = uuid4()
    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,  # type: ignore[attr-defined]
        request_id=request_id,
        role=MessageRoleEnum.USER,
        content="Hello",
    )
    assistant_event = ConversationEventFactory.build(
        conversation_id=conversation.id,  # type: ignore[attr-defined]
        request_id=request_id,
        role=MessageRoleEnum.ASSISTANT,
        content="Hi",
    )

    mock_conversation_service.get_or_raise = AsyncMock(return_value=conversation)
    mock_conversation_event_service.create = AsyncMock(side_effect=[user_event, assistant_event])
    mock_conversation_event_service.list = AsyncMock(return_value=[user_event])
    mock_orchestrator.handle = AsyncMock(
        return_value=build_orchestrator_response(
            conversation_id=conversation.id,  # type: ignore[attr-defined]
            content="Hi",
        ),
    )


async def test_extraction_is_scheduled_only_after_the_turn_commits(
    wired: ChatService,
    scheduler: MagicMock,
    mock_async_session: AsyncMock,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    conversation = ConversationFactory.build(memory_disabled=False)
    _prime_chat(
        conversation,
        mock_conversation_service,
        mock_conversation_event_service,
        mock_orchestrator,
    )

    order: list[str] = []
    mock_async_session.commit.side_effect = lambda: order.append("commit")
    scheduler.schedule.side_effect = lambda **_: order.append("schedule")

    await wired.chat(
        user_id=conversation.user_id,
        conversation_id=conversation.id,
        message="Hello",
        request_id=uuid4(),
    )

    assert order == ["commit", "schedule"]
    scheduler.schedule.assert_called_once_with(
        user_id=conversation.user_id,
        conversation_id=conversation.id,
    )


async def test_extraction_is_not_scheduled_when_the_turn_fails(
    wired: ChatService,
    scheduler: MagicMock,
    mock_async_session: AsyncMock,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    conversation = ConversationFactory.build(memory_disabled=False)
    _prime_chat(
        conversation,
        mock_conversation_service,
        mock_conversation_event_service,
        mock_orchestrator,
    )
    mock_async_session.commit.side_effect = RuntimeError("commit failed")

    with pytest.raises(RuntimeError):
        await wired.chat(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            message="Hello",
            request_id=uuid4(),
        )

    scheduler.schedule.assert_not_called()


async def test_extraction_is_not_scheduled_for_a_conversation_with_the_switch_on(
    wired: ChatService,
    scheduler: MagicMock,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    conversation = ConversationFactory.build(memory_disabled=True)
    _prime_chat(
        conversation,
        mock_conversation_service,
        mock_conversation_event_service,
        mock_orchestrator,
    )

    await wired.chat(
        user_id=conversation.user_id,
        conversation_id=conversation.id,
        message="Hello",
        request_id=uuid4(),
    )

    scheduler.schedule.assert_not_called()


async def test_chat_works_without_user_memory_wired(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    conversation = ConversationFactory.build()
    _prime_chat(
        conversation,
        mock_conversation_service,
        mock_conversation_event_service,
        mock_orchestrator,
    )

    await chat_service.chat(
        user_id=conversation.user_id,
        conversation_id=conversation.id,
        message="Hello",
        request_id=uuid4(),
    )

    request: OrchestratorRequest = mock_orchestrator.handle.await_args.kwargs["request"]
    assert request.user_memory == ()


# ----------------------------------------------------------------------
# Read path: ChatService -> OrchestratorRequest
# ----------------------------------------------------------------------


async def test_selected_memories_are_put_on_the_orchestrator_request(
    mock_async_session: AsyncMock,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
    mock_action_workflow_service: MagicMock,
    mock_usage_service: MagicMock,
    mock_conversation_summarization_service: MagicMock,
    mock_compliance_log_service: MagicMock,
) -> None:
    memory_service = MagicMock()
    memory_service.retrieve_for_prompt = AsyncMock(return_value=(_item(),))
    service = _service(
        mock_async_session,
        mock_conversation_service,
        mock_conversation_event_service,
        mock_orchestrator,
        mock_action_workflow_service,
        mock_usage_service,
        mock_conversation_summarization_service,
        mock_compliance_log_service,
        user_memory_service=memory_service,
    )
    conversation = ConversationFactory.build()
    _prime_chat(
        conversation,
        mock_conversation_service,
        mock_conversation_event_service,
        mock_orchestrator,
    )

    await service.chat(
        user_id=conversation.user_id,
        conversation_id=conversation.id,
        message="Draft a notice",
        request_id=uuid4(),
    )

    # Scoped to this user AND this conversation.
    memory_service.retrieve_for_prompt.assert_awaited_once_with(
        user_id=conversation.user_id,
        conversation_id=conversation.id,
        query="Draft a notice",
    )
    request: OrchestratorRequest = mock_orchestrator.handle.await_args.kwargs["request"]
    assert request.user_memory == (_item(),)
    # Not smuggled into history, where fit_to_budget would trim it first.
    assert all(SECRET_MEMORY not in message.content for message in request.history)


# ----------------------------------------------------------------------
# Read path: orchestrator plumbing -> agent prompt
# ----------------------------------------------------------------------


def _orchestrator_request(*, user_memory: tuple[UserMemoryContextItem, ...]) -> OrchestratorRequest:
    return OrchestratorRequest(
        request_id=uuid4(),
        conversation_id="conv_" + "1" * 32,
        current_event_id="evnt_" + "1" * 32,
        user_id="user_" + "a" * 32,
        message="Draft a legal notice",
        history=[
            ConversationMessageSchema(role=MessageRoleEnum.USER, content="earlier question"),
            ConversationMessageSchema(role=MessageRoleEnum.ASSISTANT, content="earlier answer"),
        ],
        user_memory=user_memory,
    )


def test_the_orchestrator_carries_memory_into_the_conversation_and_the_planning_context() -> None:
    request = _orchestrator_request(user_memory=(_item(),))

    conversation = AIOrchestrator._build_conversation(request=request)
    context = AIOrchestrator._build_context(request=request)

    assert conversation.user_memory == (_item(),)
    assert context.conversation.user_memory == (_item(),)
    # Memory is not a message: the conversation is history + the current turn.
    assert [message.content for message in conversation.messages] == [
        "earlier question",
        "earlier answer",
        "Draft a legal notice",
    ]


def _built_prompt(request: OrchestratorRequest) -> tuple[str, ...]:
    conversation = AIOrchestrator._build_conversation(request=request)
    prompt = LegalPromptBuilder().build(
        request=AgentRequestDTO(
            conversation=conversation,
            instruction="Draft a legal notice",
            context=build_agent_context(),
        ),
        context=(),
        model="llama-3.3-70b-versatile",
    )

    return tuple(message.content for message in prompt.messages)


def test_with_the_switch_off_the_memory_reaches_the_built_prompt() -> None:
    contents = _built_prompt(_orchestrator_request(user_memory=(_item(),)))

    assert any(SECRET_MEMORY in content for content in contents)


# ----------------------------------------------------------------------
# The per-conversation switch suppresses INJECTION, end to end
# ----------------------------------------------------------------------


def _real_memory_service(*, switch_on: bool) -> tuple[UserMemoryService, MagicMock]:
    """
    A real UserMemoryService whose repositories are faked so that a
    profile memory (always included, no similarity needed) and a
    similarity match both exist for this user.
    """

    now = datetime.now(UTC)
    profile = SimpleNamespace(
        id="umem_" + "b" * 32,
        kind=UserMemoryKindEnum.PROFILE.value,
        content="Practises before the Delhi High Court",
        last_used_at=now,
    )
    match = SimpleNamespace(
        id="umem_" + "c" * 32,
        kind=UserMemoryKindEnum.PREFERENCE.value,
        content=SECRET_MEMORY,
        last_used_at=now,
    )

    repository = MagicMock()
    repository.list_live_by_kind = AsyncMock(return_value=[profile])
    repository.search_similar = AsyncMock(return_value=[(match, 0.99)])
    repository.touch = AsyncMock(return_value=2)

    user_repository = MagicMock()
    user_repository.get = AsyncMock(return_value=SimpleNamespace(memory_enabled=True))

    conversation_repository = MagicMock()
    conversation_repository.get_memory_disabled = AsyncMock(return_value=switch_on)

    embedding_provider = MagicMock()
    embedding_provider.metadata = EmbeddingMetadata(model_name=MODEL, dimension=384)
    embedding_provider.embed = AsyncMock(return_value=[[0.1] * 384])

    session = MagicMock()
    session.begin_nested = MagicMock(side_effect=lambda: _Savepoint())

    service = UserMemoryService(
        session=session,
        repository=repository,
        user_repository=user_repository,
        conversation_repository=conversation_repository,
        embedding_provider=embedding_provider,
        compliance_log=MagicMock(),
    )

    return service, repository


async def _chat_prompt_contents(
    *,
    switch_on: bool,
    mock_async_session: AsyncMock,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
    mock_action_workflow_service: MagicMock,
    mock_usage_service: MagicMock,
    mock_conversation_summarization_service: MagicMock,
    mock_compliance_log_service: MagicMock,
) -> tuple[tuple[str, ...], MagicMock]:
    memory_service, repository = _real_memory_service(switch_on=switch_on)
    service = _service(
        mock_async_session,
        mock_conversation_service,
        mock_conversation_event_service,
        mock_orchestrator,
        mock_action_workflow_service,
        mock_usage_service,
        mock_conversation_summarization_service,
        mock_compliance_log_service,
        user_memory_service=memory_service,
    )
    conversation = ConversationFactory.build(memory_disabled=switch_on)
    _prime_chat(
        conversation,
        mock_conversation_service,
        mock_conversation_event_service,
        mock_orchestrator,
    )

    await service.chat(
        user_id=conversation.user_id,
        conversation_id=conversation.id,
        message="Draft a legal notice",
        request_id=uuid4(),
    )

    request: OrchestratorRequest = mock_orchestrator.handle.await_args.kwargs["request"]

    return _built_prompt(request), repository


async def test_switch_on_keeps_a_matching_memory_out_of_the_built_prompt(
    mock_async_session: AsyncMock,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
    mock_action_workflow_service: MagicMock,
    mock_usage_service: MagicMock,
    mock_conversation_summarization_service: MagicMock,
    mock_compliance_log_service: MagicMock,
) -> None:
    deps = {
        "mock_async_session": mock_async_session,
        "mock_conversation_service": mock_conversation_service,
        "mock_conversation_event_service": mock_conversation_event_service,
        "mock_orchestrator": mock_orchestrator,
        "mock_action_workflow_service": mock_action_workflow_service,
        "mock_usage_service": mock_usage_service,
        "mock_conversation_summarization_service": mock_conversation_summarization_service,
        "mock_compliance_log_service": mock_compliance_log_service,
    }

    # Control: switch OFF -- the same memories DO reach the prompt, so the
    # assertion below is meaningful (the memory really would match).
    contents_off, _ = await _chat_prompt_contents(switch_on=False, **deps)

    assert any(SECRET_MEMORY in content for content in contents_off)
    assert any("Delhi High Court" in content for content in contents_off)

    # Switch ON: nothing from memory, not even the always-included profile
    # item, and the database was never searched.
    contents_on, repository = await _chat_prompt_contents(switch_on=True, **deps)

    assert not any(SECRET_MEMORY in content for content in contents_on)
    assert not any("Delhi High Court" in content for content in contents_on)
    assert not any("<user_memory>" in content for content in contents_on)
    repository.search_similar.assert_not_awaited()
    repository.list_live_by_kind.assert_not_awaited()
    repository.touch.assert_not_awaited()
