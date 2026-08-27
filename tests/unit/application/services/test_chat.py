"""
Unit tests for ChatService.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from agentic.orchestration.schemas.request import OrchestratorRequest
from application.services.chat import ChatService
from application.services.internal_dto.chat import ChatResultDTO
from core.enums import MessageRoleEnum
from core.exceptions.httpx import ConversationInactiveError, NotFoundError
from tests.builders.agentic.orchestrator import build_orchestrator_response
from tests.factories.conversation import ConversationFactory
from tests.factories.conversation_event import ConversationEventFactory
from tests.helpers.identifiers import unknown_conversation_id, unknown_user_id

TEST_MESSAGE = "Hello"


def _request_id():
    """
    Generate a request identifier for a chat request.
    """

    return uuid4()


@pytest.mark.asyncio
async def test_chat_returns_chat_result(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    """
    It should process a chat request successfully.
    """

    conversation = ConversationFactory.build()
    request_id = uuid4()

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        request_id=request_id,
        role=MessageRoleEnum.USER,
        content="Hello",
    )

    response = build_orchestrator_response(
        conversation_id=conversation.id,
        content="Hello!",
    )

    assistant_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        request_id=request_id,
        parent_event_id=user_event.id,
        role=MessageRoleEnum.ASSISTANT,
        content=response.content,
        event_metadata=response.metadata.model_dump(
            mode="json",
        ),
    )

    mock_conversation_service.get_or_raise = AsyncMock(
        return_value=conversation,
    )

    mock_conversation_event_service.create = AsyncMock(
        side_effect=[
            user_event,
            assistant_event,
        ],
    )

    mock_conversation_event_service.list = AsyncMock(
        return_value=[],
    )

    mock_orchestrator.handle = AsyncMock(
        return_value=response,
    )

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    result = await chat_service.chat(
        user_id=conversation.user_id,
        conversation_id=conversation.id,
        message="Hello",
        request_id=request_id,
    )

    assert isinstance(
        result,
        ChatResultDTO,
    )

    assert result.conversation is conversation
    assert result.user_event is user_event
    assert result.assistant_event is assistant_event
    assert result.response is response

    mock_conversation_service.get_or_raise.assert_awaited_once_with(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
    )

    mock_conversation_event_service.create.assert_any_await(
        conversation_id=conversation.id,
        request_id=request_id,
        role=MessageRoleEnum.USER,
        content="Hello",
    )

    mock_orchestrator.handle.assert_awaited_once()

    orchestration_request = mock_orchestrator.handle.await_args.kwargs["request"]

    assert isinstance(
        orchestration_request,
        OrchestratorRequest,
    )

    assert orchestration_request.request_id == request_id
    assert orchestration_request.conversation_id == conversation.id
    assert orchestration_request.user_id == conversation.user_id
    assert orchestration_request.message == "Hello"
    assert orchestration_request.history == []
    assert orchestration_request.attachments == []

    mock_conversation_event_service.create.assert_any_await(
        conversation_id=conversation.id,
        request_id=request_id,
        parent_event_id=user_event.id,
        role=MessageRoleEnum.ASSISTANT,
        content=response.content,
        metadata=response.metadata.model_dump(
            mode="json",
        ),
    )

    chat_service.commit.assert_awaited_once_with()
    chat_service.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_raises_when_conversation_does_not_exist(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    """
    It should fail when the conversation does not exist.
    """

    user_id = unknown_user_id()
    conversation_id = unknown_conversation_id()
    request_id = _request_id()

    error = NotFoundError(
        message="Conversation not found.",
    )

    mock_conversation_service.get_or_raise = AsyncMock(
        side_effect=error,
    )

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(
        NotFoundError,
        match="Conversation not found.",
    ):
        await chat_service.chat(
            user_id=user_id,
            conversation_id=conversation_id,
            message=TEST_MESSAGE,
            request_id=request_id,
        )

    mock_conversation_service.get_or_raise.assert_awaited_once_with(
        conversation_id=conversation_id,
        user_id=user_id,
    )

    mock_conversation_event_service.create.assert_not_called()
    mock_orchestrator.handle.assert_not_called()

    chat_service.commit.assert_not_awaited()
    chat_service.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_raises_when_conversation_is_inactive(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    """
    It should fail when the conversation is inactive.
    """

    conversation = ConversationFactory.build(
        archived=True,
    )

    request_id = _request_id()

    mock_conversation_service.get_or_raise = AsyncMock(
        side_effect=ConversationInactiveError(
            "Conversation is inactive.",
        ),
    )

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(
        ConversationInactiveError,
        match="Conversation is inactive.",
    ):
        await chat_service.chat(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
            request_id=request_id,
        )

    mock_conversation_service.get_or_raise.assert_awaited_once_with(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
    )

    mock_conversation_event_service.create.assert_not_called()
    mock_orchestrator.handle.assert_not_called()

    chat_service.commit.assert_not_awaited()
    chat_service.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_rolls_back_when_creating_user_event_fails(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    """
    It should roll back when creating the user event fails.
    """

    conversation = ConversationFactory.build()
    request_id = _request_id()

    mock_conversation_service.get_or_raise = AsyncMock(
        return_value=conversation,
    )

    mock_conversation_event_service.create = AsyncMock(
        side_effect=SQLAlchemyError(
            "Failed to create user event.",
        ),
    )

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(SQLAlchemyError):
        await chat_service.chat(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
            request_id=request_id,
        )

    mock_conversation_service.get_or_raise.assert_awaited_once_with(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
    )

    mock_conversation_event_service.create.assert_awaited_once_with(
        conversation_id=conversation.id,
        request_id=request_id,
        role=MessageRoleEnum.USER,
        content=TEST_MESSAGE,
    )

    mock_orchestrator.handle.assert_not_called()

    chat_service.rollback.assert_awaited_once()
    chat_service.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_rolls_back_when_agent_fails(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    """
    It should roll back when the orchestrator fails.
    """

    conversation = ConversationFactory.build()
    request_id = _request_id()

    mock_conversation_service.get_or_raise = AsyncMock(
        return_value=conversation,
    )

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        request_id=request_id,
        role=MessageRoleEnum.USER,
        content=TEST_MESSAGE,
    )

    mock_conversation_event_service.create = AsyncMock(
        return_value=user_event,
    )

    mock_conversation_event_service.list = AsyncMock(
        return_value=[],
    )

    mock_orchestrator.handle = AsyncMock(
        side_effect=SQLAlchemyError(
            "Agent execution failed.",
        ),
    )

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(SQLAlchemyError):
        await chat_service.chat(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
            request_id=request_id,
        )

    mock_conversation_service.get_or_raise.assert_awaited_once_with(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
    )

    mock_conversation_event_service.create.assert_awaited_once_with(
        conversation_id=conversation.id,
        request_id=request_id,
        role=MessageRoleEnum.USER,
        content=TEST_MESSAGE,
    )

    mock_orchestrator.handle.assert_awaited_once()

    chat_service.rollback.assert_awaited_once()
    chat_service.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_rolls_back_when_creating_assistant_event_fails(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    """
    It should roll back when creating the assistant event fails.
    """

    conversation = ConversationFactory.build()
    request_id = _request_id()

    mock_conversation_service.get_or_raise = AsyncMock(
        return_value=conversation,
    )

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        request_id=request_id,
        role=MessageRoleEnum.USER,
        content=TEST_MESSAGE,
    )

    mock_conversation_event_service.create = AsyncMock(
        side_effect=[
            user_event,
            SQLAlchemyError(
                "Failed to create assistant event.",
            ),
        ],
    )

    mock_conversation_event_service.list = AsyncMock(
        return_value=[],
    )

    response = build_orchestrator_response(
        conversation_id=conversation.id,
        content="Legal answer",
    )

    mock_orchestrator.handle = AsyncMock(
        return_value=response,
    )

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(SQLAlchemyError):
        await chat_service.chat(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
            request_id=request_id,
        )

    mock_conversation_service.get_or_raise.assert_awaited_once_with(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
    )

    assert mock_conversation_event_service.create.await_count == 2

    mock_conversation_event_service.create.assert_any_await(
        conversation_id=conversation.id,
        request_id=request_id,
        role=MessageRoleEnum.USER,
        content=TEST_MESSAGE,
    )

    mock_orchestrator.handle.assert_awaited_once()

    chat_service.rollback.assert_awaited_once()
    chat_service.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_rolls_back_when_commit_fails(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    """
    It should roll back when committing the transaction fails.
    """

    conversation = ConversationFactory.build()
    request_id = _request_id()

    mock_conversation_service.get_or_raise = AsyncMock(
        return_value=conversation,
    )

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        request_id=request_id,
        role=MessageRoleEnum.USER,
        content=TEST_MESSAGE,
    )

    assistant_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        request_id=request_id,
        parent_event_id=user_event.id,
        role=MessageRoleEnum.ASSISTANT,
        content="Legal answer",
    )

    mock_conversation_event_service.create = AsyncMock(
        side_effect=[
            user_event,
            assistant_event,
        ],
    )

    mock_conversation_event_service.list = AsyncMock(
        return_value=[],
    )

    response = build_orchestrator_response(
        conversation_id=conversation.id,
        content="Legal answer",
    )

    mock_orchestrator.handle = AsyncMock(
        return_value=response,
    )

    chat_service.commit = AsyncMock(
        side_effect=SQLAlchemyError(
            "Commit failed.",
        ),
    )

    chat_service.rollback = AsyncMock()

    with pytest.raises(SQLAlchemyError):
        await chat_service.chat(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
            request_id=request_id,
        )

    mock_conversation_service.get_or_raise.assert_awaited_once_with(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
    )

    assert mock_conversation_event_service.create.await_count == 2

    mock_orchestrator.handle.assert_awaited_once()

    chat_service.commit.assert_awaited_once()
    chat_service.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_chat_raises_when_conversation_does_not_exist(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    """
    It should fail when the conversation does not exist.
    """

    conversation_id = unknown_conversation_id()
    user_id = unknown_user_id()
    request_id = _request_id()

    mock_conversation_service.get_or_raise = AsyncMock(
        side_effect=NotFoundError(
            message="Conversation not found.",
        ),
    )

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(
        NotFoundError,
        match="Conversation not found.",
    ):
        async for _ in chat_service.stream_chat(
            user_id=user_id,
            conversation_id=conversation_id,
            message=TEST_MESSAGE,
            request_id=request_id,
        ):
            pass

    mock_conversation_service.get_or_raise.assert_awaited_once_with(
        conversation_id=conversation_id,
        user_id=user_id,
    )

    mock_conversation_event_service.create.assert_not_called()
    mock_orchestrator.stream.assert_not_called()

    chat_service.commit.assert_not_awaited()
    chat_service.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_chat_raises_when_conversation_is_archived(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    """
    It should fail when the conversation is archived.
    """

    conversation_id = unknown_conversation_id()
    user_id = unknown_user_id()
    request_id = _request_id()

    mock_conversation_service.get_or_raise = AsyncMock(
        side_effect=ConversationInactiveError(
            message="Conversation is inactive.",
        ),
    )

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(
        ConversationInactiveError,
        match="Conversation is inactive.",
    ):
        async for _ in chat_service.stream_chat(
            user_id=user_id,
            conversation_id=conversation_id,
            message=TEST_MESSAGE,
            request_id=request_id,
        ):
            pass

    mock_conversation_service.get_or_raise.assert_awaited_once_with(
        conversation_id=conversation_id,
        user_id=user_id,
    )

    mock_conversation_event_service.create.assert_not_called()
    mock_orchestrator.stream.assert_not_called()

    chat_service.commit.assert_not_awaited()
    chat_service.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_chat_rolls_back_when_creating_user_event_fails(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    """
    It should roll back when creating the user event fails.
    """

    conversation = ConversationFactory.build()
    request_id = _request_id()

    mock_conversation_service.get_or_raise = AsyncMock(
        return_value=conversation,
    )

    mock_conversation_event_service.create = AsyncMock(
        side_effect=SQLAlchemyError(
            "Failed to create user event.",
        ),
    )

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(SQLAlchemyError):
        async for _ in chat_service.stream_chat(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
            request_id=request_id,
        ):
            pass

    mock_conversation_service.get_or_raise.assert_awaited_once_with(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
    )

    mock_conversation_event_service.create.assert_awaited_once_with(
        conversation_id=conversation.id,
        request_id=request_id,
        role=MessageRoleEnum.USER,
        content=TEST_MESSAGE,
    )

    mock_orchestrator.stream.assert_not_called()

    chat_service.rollback.assert_awaited_once()
    chat_service.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_chat_rolls_back_when_agent_fails(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    """
    It should roll back when the orchestrator fails while streaming.
    """

    conversation = ConversationFactory.build()
    request_id = _request_id()

    mock_conversation_service.get_or_raise = AsyncMock(
        return_value=conversation,
    )

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        request_id=request_id,
        role=MessageRoleEnum.USER,
        content=TEST_MESSAGE,
    )

    mock_conversation_event_service.create = AsyncMock(
        return_value=user_event,
    )

    mock_conversation_event_service.list = AsyncMock(
        return_value=[],
    )

    mock_orchestrator.stream = MagicMock(
        side_effect=SQLAlchemyError(
            "Agent execution failed.",
        ),
    )

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(SQLAlchemyError):
        async for _ in chat_service.stream_chat(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
            request_id=request_id,
        ):
            pass

    mock_conversation_service.get_or_raise.assert_awaited_once_with(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
    )

    mock_conversation_event_service.create.assert_awaited_once_with(
        conversation_id=conversation.id,
        request_id=request_id,
        role=MessageRoleEnum.USER,
        content=TEST_MESSAGE,
    )

    mock_conversation_event_service.list.assert_awaited_once_with(
        conversation_id=conversation.id,
    )

    mock_orchestrator.stream.assert_called_once()

    chat_service.rollback.assert_awaited_once()
    chat_service.commit.assert_not_awaited()
