"""
Unit tests for ChatService.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call

import pytest

from src.core.enums import MessageRole
from src.core.exceptions.httpx import NotFoundError
from src.services.chat import ChatService
from src.services.results.chat import ChatResult
from tests.builders.agent import (
    build_agent_chunk,
    build_agent_response,
    build_token_usage,
)
from tests.factories.conversation import ConversationFactory
from tests.factories.conversation_event import ConversationEventFactory
from tests.helpers.agent_stream import DummyAgentStream

TEST_MESSAGE = "Hello"


@pytest.mark.asyncio
async def test_chat_returns_chat_result(
    chat_service: ChatService,
    mock_conversation_repository: MagicMock,
    mock_conversation_event_repository: MagicMock,
    mock_agent: MagicMock,
) -> None:
    """
    It should process a chat request successfully.
    """

    conversation = ConversationFactory.build()

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        role=MessageRole.USER,
    )

    assistant_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        parent_event_id=user_event.id,
        role=MessageRole.ASSISTANT,
    )

    response = build_agent_response()

    mock_conversation_repository.get.return_value = conversation

    mock_conversation_event_repository.create.side_effect = [
        user_event,
        assistant_event,
    ]

    mock_agent.answer.return_value = response

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    result = await chat_service.chat(
        conversation_id=conversation.id,
        message="Hello",
    )

    assert isinstance(
        result,
        ChatResult,
    )

    assert result.conversation is conversation
    assert result.user_event is user_event
    assert result.assistant_event is assistant_event

    mock_conversation_repository.get.assert_awaited_once_with(
        conversation.id,
    )

    assert mock_conversation_event_repository.create.await_count == 2

    mock_agent.answer.assert_awaited_once()

    request = mock_agent.answer.await_args.kwargs["request"]

    assert request.question == "Hello"
    assert request.history == []

    chat_service.commit.assert_awaited_once_with()
    chat_service.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_raises_when_conversation_does_not_exist(
    chat_service: ChatService,
    mock_conversation_repository: MagicMock,
    mock_conversation_event_repository: MagicMock,
    mock_agent: MagicMock,
) -> None:
    """
    It should fail when the conversation does not exist.
    """

    mock_conversation_repository.get.return_value = None

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(
        NotFoundError,
        match="Conversation not found.",
    ):
        await chat_service.chat(
            conversation_id="conversation_123",
            message=TEST_MESSAGE,
        )

    mock_conversation_repository.get.assert_awaited_once_with(
        "conversation_123",
    )

    mock_conversation_event_repository.create.assert_not_called()

    mock_agent.answer.assert_not_called()

    chat_service.commit.assert_not_awaited()
    chat_service.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_chat_raises_when_conversation_is_inactive(
    chat_service: ChatService,
    mock_conversation_repository: MagicMock,
    mock_conversation_event_repository: MagicMock,
    mock_agent: MagicMock,
) -> None:
    """
    It should fail when the conversation is inactive.
    """

    conversation = ConversationFactory.build(
        archived=True,
    )

    mock_conversation_repository.get.return_value = conversation

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(
        NotFoundError,
        match="Conversation is inactive.",
    ):
        await chat_service.chat(
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
        )

    mock_conversation_repository.get.assert_awaited_once_with(
        conversation.id,
    )

    mock_conversation_event_repository.create.assert_not_called()

    mock_agent.answer.assert_not_called()

    chat_service.commit.assert_not_awaited()
    chat_service.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_chat_rolls_back_when_creating_user_event_fails(
    chat_service: ChatService,
    mock_conversation_repository: MagicMock,
    mock_conversation_event_repository: MagicMock,
    mock_agent: MagicMock,
) -> None:
    """
    It should roll back when creating the user event fails.
    """

    conversation = ConversationFactory.build()

    mock_conversation_repository.get.return_value = conversation

    mock_conversation_event_repository.create.side_effect = RuntimeError(
        "Database error",
    )

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(
        RuntimeError,
        match="Database error",
    ):
        await chat_service.chat(
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
        )

    mock_conversation_repository.get.assert_awaited_once_with(
        conversation.id,
    )

    mock_conversation_event_repository.create.assert_awaited_once_with(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=TEST_MESSAGE,
    )

    mock_agent.answer.assert_not_called()

    chat_service.commit.assert_not_awaited()
    chat_service.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_chat_rolls_back_when_agent_fails(
    chat_service: ChatService,
    mock_conversation_repository: MagicMock,
    mock_conversation_event_repository: MagicMock,
    mock_agent: MagicMock,
) -> None:
    """
    It should roll back when the agent fails.
    """

    conversation = ConversationFactory.build()

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        role=MessageRole.USER,
    )

    mock_conversation_repository.get.return_value = conversation

    mock_conversation_event_repository.create.return_value = user_event

    mock_agent.answer.side_effect = RuntimeError(
        "Agent failed",
    )

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(
        RuntimeError,
        match="Agent failed",
    ):
        await chat_service.chat(
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
        )

    mock_conversation_repository.get.assert_awaited_once_with(
        conversation.id,
    )

    mock_conversation_event_repository.create.assert_awaited_once_with(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=TEST_MESSAGE,
    )

    mock_agent.answer.assert_awaited_once()

    request = mock_agent.answer.await_args.kwargs["request"]

    assert request.question == TEST_MESSAGE
    assert request.history == []

    chat_service.commit.assert_not_awaited()
    chat_service.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_chat_rolls_back_when_creating_assistant_event_fails(
    chat_service: ChatService,
    mock_conversation_repository: MagicMock,
    mock_conversation_event_repository: MagicMock,
    mock_agent: MagicMock,
) -> None:
    """
    It should roll back when creating the assistant event fails.
    """

    conversation = ConversationFactory.build()

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        role=MessageRole.USER,
    )

    response = build_agent_response()

    mock_conversation_repository.get.return_value = conversation

    mock_conversation_event_repository.create.side_effect = [
        user_event,
        RuntimeError(
            "Database error",
        ),
    ]

    mock_agent.answer.return_value = response

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(
        RuntimeError,
        match="Database error",
    ):
        await chat_service.chat(
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
        )

    mock_conversation_repository.get.assert_awaited_once_with(
        conversation.id,
    )

    assert mock_conversation_event_repository.create.await_count == 2

    mock_agent.answer.assert_awaited_once()

    chat_service.commit.assert_not_awaited()
    chat_service.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_chat_rolls_back_when_commit_fails(
    chat_service: ChatService,
    mock_conversation_repository: MagicMock,
    mock_conversation_event_repository: MagicMock,
    mock_agent: MagicMock,
) -> None:
    """
    It should roll back when committing the transaction fails.
    """

    conversation = ConversationFactory.build()

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        role=MessageRole.USER,
    )

    assistant_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        parent_event_id=user_event.id,
        role=MessageRole.ASSISTANT,
    )

    response = build_agent_response()

    mock_conversation_repository.get.return_value = conversation

    mock_conversation_event_repository.create.side_effect = [
        user_event,
        assistant_event,
    ]

    mock_agent.answer.return_value = response

    chat_service.commit = AsyncMock(
        side_effect=RuntimeError(
            "Commit failed",
        ),
    )

    chat_service.rollback = AsyncMock()

    with pytest.raises(
        RuntimeError,
        match="Commit failed",
    ):
        await chat_service.chat(
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
        )

    mock_conversation_repository.get.assert_awaited_once_with(
        conversation.id,
    )

    assert mock_conversation_event_repository.create.await_args_list == [
        call(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=TEST_MESSAGE,
        ),
        call(
            conversation_id=conversation.id,
            parent_event_id=user_event.id,
            role=MessageRole.ASSISTANT,
            content=response.content,
            metadata=chat_service._build_response_metadata(
                response,
            ),
        ),
    ]

    mock_agent.answer.assert_awaited_once()

    chat_service.commit.assert_awaited_once_with()
    chat_service.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_stream_chat_returns_chat_stream_chunks(
    chat_service: ChatService,
    mock_conversation_repository: MagicMock,
    mock_conversation_event_repository: MagicMock,
    mock_agent: MagicMock,
) -> None:
    """
    It should stream chat response chunks.
    """

    conversation = ConversationFactory.build()

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        role=MessageRole.USER,
    )

    assistant_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        parent_event_id=user_event.id,
        role=MessageRole.ASSISTANT,
    )

    response = build_agent_response()

    stream = DummyAgentStream(
        response=response,
        chunks=[
            build_agent_chunk(
                content="Hello",
            ),
            build_agent_chunk(
                content=" World",
                is_final=True,
            ),
        ],
    )

    mock_conversation_repository.get.return_value = conversation

    mock_conversation_event_repository.create.side_effect = [
        user_event,
        assistant_event,
    ]

    mock_agent.stream_answer.return_value = stream

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    chunks = [
        chunk
        async for chunk in chat_service.stream_chat(
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
        )
    ]

    assert len(chunks) == 2

    assert chunks[0].content == "Hello"
    assert chunks[0].is_final is False

    assert chunks[1].content == " World"
    assert chunks[1].is_final is True

    mock_conversation_repository.get.assert_awaited_once_with(
        conversation.id,
    )

    mock_agent.stream_answer.assert_called_once()

    request = mock_agent.stream_answer.call_args.kwargs["request"]

    assert request.question == TEST_MESSAGE
    assert request.history == []

    assert mock_conversation_event_repository.create.await_args_list == [
        call(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=TEST_MESSAGE,
        ),
        call(
            conversation_id=conversation.id,
            parent_event_id=user_event.id,
            role=MessageRole.ASSISTANT,
            content=response.content,
            metadata=chat_service._build_response_metadata(
                response,
            ),
        ),
    ]

    assert chat_service.commit.await_count == 2

    chat_service.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_chat_raises_when_conversation_does_not_exist(
    chat_service: ChatService,
    mock_conversation_repository: MagicMock,
    mock_conversation_event_repository: MagicMock,
    mock_agent: MagicMock,
) -> None:
    """
    It should fail when the conversation does not exist.
    """

    mock_conversation_repository.get.return_value = None

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(
        NotFoundError,
        match="Conversation not found.",
    ):
        [
            chunk
            async for chunk in chat_service.stream_chat(
                conversation_id="conversation_123",
                message=TEST_MESSAGE,
            )
        ]

    mock_conversation_repository.get.assert_awaited_once_with(
        "conversation_123",
    )

    mock_conversation_event_repository.create.assert_not_called()
    mock_agent.stream_answer.assert_not_called()

    chat_service.commit.assert_not_awaited()
    chat_service.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_stream_chat_raises_when_conversation_is_archived(
    chat_service: ChatService,
    mock_conversation_repository: MagicMock,
    mock_conversation_event_repository: MagicMock,
    mock_agent: MagicMock,
) -> None:
    """
    It should fail when the conversation is archived.
    """

    conversation = ConversationFactory.build(
        archived=True,
    )

    mock_conversation_repository.get.return_value = conversation

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(
        NotFoundError,
        match="Conversation is inactive.",
    ):
        async for _ in chat_service.stream_chat(
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
        ):
            pass

    mock_conversation_repository.get.assert_awaited_once_with(
        conversation.id,
    )

    mock_conversation_event_repository.create.assert_not_called()
    mock_agent.stream_answer.assert_not_called()

    chat_service.commit.assert_not_awaited()
    chat_service.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_stream_chat_rolls_back_when_creating_user_event_fails(
    chat_service: ChatService,
    mock_conversation_repository: MagicMock,
    mock_conversation_event_repository: MagicMock,
    mock_agent: MagicMock,
) -> None:
    """
    It should roll back when creating the user event fails.
    """

    conversation = ConversationFactory.build()

    mock_conversation_repository.get.return_value = conversation

    mock_conversation_event_repository.create.side_effect = RuntimeError(
        "Database error",
    )

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(
        RuntimeError,
        match="Database error",
    ):
        _ = [
            chunk
            async for chunk in chat_service.stream_chat(
                conversation_id=conversation.id,
                message=TEST_MESSAGE,
            )
        ]

    mock_conversation_repository.get.assert_awaited_once_with(
        conversation.id,
    )

    mock_conversation_event_repository.create.assert_awaited_once_with(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=TEST_MESSAGE,
    )

    mock_agent.stream_answer.assert_not_called()

    chat_service.commit.assert_not_awaited()
    chat_service.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_stream_chat_rolls_back_when_agent_fails(
    chat_service: ChatService,
    mock_conversation_repository: MagicMock,
    mock_conversation_event_repository: MagicMock,
    mock_agent: MagicMock,
) -> None:
    """
    It should roll back when the agent fails while streaming.
    """

    conversation = ConversationFactory.build()

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        role=MessageRole.USER,
    )

    mock_conversation_repository.get.return_value = conversation

    mock_conversation_event_repository.create.return_value = user_event

    mock_agent.stream_answer.side_effect = RuntimeError(
        "Agent failed",
    )

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(
        RuntimeError,
        match="Agent failed",
    ):
        _ = [
            chunk
            async for chunk in chat_service.stream_chat(
                conversation_id=conversation.id,
                message=TEST_MESSAGE,
            )
        ]

    mock_conversation_repository.get.assert_awaited_once_with(
        conversation.id,
    )

    mock_conversation_event_repository.create.assert_awaited_once_with(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=TEST_MESSAGE,
    )

    mock_agent.stream_answer.assert_called_once()

    request = mock_agent.stream_answer.call_args.kwargs["request"]

    assert request.question == TEST_MESSAGE
    assert request.history == []

    #
    # First commit (user event) succeeds.
    # Second commit is never reached.
    #
    assert chat_service.commit.await_count == 1

    chat_service.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_stream_chat_rolls_back_when_creating_assistant_event_fails(
    chat_service: ChatService,
    mock_conversation_repository: MagicMock,
    mock_conversation_event_repository: MagicMock,
    mock_agent: MagicMock,
) -> None:
    """
    It should roll back when creating the assistant event fails.
    """

    conversation = ConversationFactory.build()

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        role=MessageRole.USER,
    )

    response = build_agent_response()

    stream = DummyAgentStream(
        response=response,
        chunks=[
            build_agent_chunk(
                content="Hello",
            ),
            build_agent_chunk(
                content=" World",
                is_final=True,
            ),
        ],
    )

    mock_conversation_repository.get.return_value = conversation

    mock_conversation_event_repository.create.side_effect = [
        user_event,
        RuntimeError(
            "Database error",
        ),
    ]

    mock_agent.stream_answer.return_value = stream

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(
        RuntimeError,
        match="Database error",
    ):
        _ = [
            chunk
            async for chunk in chat_service.stream_chat(
                conversation_id=conversation.id,
                message=TEST_MESSAGE,
            )
        ]

    mock_conversation_repository.get.assert_awaited_once_with(
        conversation.id,
    )

    mock_agent.stream_answer.assert_called_once()

    assert mock_conversation_event_repository.create.await_args_list == [
        call(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=TEST_MESSAGE,
        ),
        call(
            conversation_id=conversation.id,
            parent_event_id=user_event.id,
            role=MessageRole.ASSISTANT,
            content=response.content,
            metadata=chat_service._build_response_metadata(
                response,
            ),
        ),
    ]

    #
    # First commit succeeds.
    # Final commit is never reached.
    #
    assert chat_service.commit.await_count == 1

    chat_service.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_stream_chat_rolls_back_when_final_commit_fails(
    chat_service: ChatService,
    mock_conversation_repository: MagicMock,
    mock_conversation_event_repository: MagicMock,
    mock_agent: MagicMock,
) -> None:
    """
    It should roll back when the final commit fails.
    """

    conversation = ConversationFactory.build()

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        role=MessageRole.USER,
    )

    assistant_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        parent_event_id=user_event.id,
        role=MessageRole.ASSISTANT,
    )

    response = build_agent_response()

    stream = DummyAgentStream(
        response=response,
        chunks=[
            build_agent_chunk(
                content="Hello",
            ),
            build_agent_chunk(
                content=" World",
                is_final=True,
            ),
        ],
    )

    mock_conversation_repository.get.return_value = conversation

    mock_conversation_event_repository.create.side_effect = [
        user_event,
        assistant_event,
    ]

    mock_agent.stream_answer.return_value = stream

    chat_service.commit = AsyncMock(
        side_effect=[
            None,
            RuntimeError(
                "Commit failed",
            ),
        ],
    )

    chat_service.rollback = AsyncMock()

    with pytest.raises(
        RuntimeError,
        match="Commit failed",
    ):
        _ = [
            chunk
            async for chunk in chat_service.stream_chat(
                conversation_id=conversation.id,
                message=TEST_MESSAGE,
            )
        ]

    mock_conversation_repository.get.assert_awaited_once_with(
        conversation.id,
    )

    mock_agent.stream_answer.assert_called_once()

    request = mock_agent.stream_answer.call_args.kwargs["request"]

    assert request.question == TEST_MESSAGE
    assert request.history == []

    assert mock_conversation_event_repository.create.await_args_list == [
        call(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=TEST_MESSAGE,
        ),
        call(
            conversation_id=conversation.id,
            parent_event_id=user_event.id,
            role=MessageRole.ASSISTANT,
            content=response.content,
            metadata=chat_service._build_response_metadata(
                response,
            ),
        ),
    ]

    #
    # Both commits are attempted.
    #
    assert chat_service.commit.await_count == 2

    chat_service.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_get_conversation_returns_conversation(
    chat_service: ChatService,
    mock_conversation_repository: MagicMock,
) -> None:
    """
    It should return the active conversation.
    """

    conversation = ConversationFactory.build()

    mock_conversation_repository.get.return_value = conversation

    found = await chat_service._get_conversation(
        conversation.id,
    )

    assert found is conversation

    mock_conversation_repository.get.assert_awaited_once_with(
        conversation.id,
    )


@pytest.mark.asyncio
async def test_get_conversation_raises_when_missing(
    chat_service: ChatService,
    mock_conversation_repository: MagicMock,
) -> None:
    """
    It should fail when the conversation does not exist.
    """

    mock_conversation_repository.get.return_value = None

    with pytest.raises(
        NotFoundError,
        match="Conversation not found.",
    ):
        await chat_service._get_conversation(
            "conversation_123",
        )

    mock_conversation_repository.get.assert_awaited_once_with(
        "conversation_123",
    )


@pytest.mark.asyncio
async def test_get_conversation_raises_when_inactive(
    chat_service: ChatService,
    mock_conversation_repository: MagicMock,
) -> None:
    """
    It should fail when the conversation is inactive.
    """

    conversation = ConversationFactory.build(
        archived=True,
    )

    mock_conversation_repository.get.return_value = conversation

    with pytest.raises(
        NotFoundError,
        match="Conversation is inactive.",
    ):
        await chat_service._get_conversation(
            conversation.id,
        )

    mock_conversation_repository.get.assert_awaited_once_with(
        conversation.id,
    )


@pytest.mark.asyncio
async def test_create_assistant_event_creates_event(
    chat_service: ChatService,
    mock_conversation_event_repository: MagicMock,
) -> None:
    """
    It should create an assistant conversation event.
    """

    conversation = ConversationFactory.build()

    parent_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        role=MessageRole.USER,
    )

    assistant_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        parent_event_id=parent_event.id,
        role=MessageRole.ASSISTANT,
    )

    response = build_agent_response()

    mock_conversation_event_repository.create.return_value = assistant_event

    created = await chat_service._create_assistant_event(
        conversation=conversation,
        parent_event=parent_event,
        response=response,
    )

    assert created is assistant_event

    mock_conversation_event_repository.create.assert_awaited_once_with(
        conversation_id=conversation.id,
        parent_event_id=parent_event.id,
        role=MessageRole.ASSISTANT,
        content=response.content,
        metadata=chat_service._build_response_metadata(
            response,
        ),
    )


def test_build_response_metadata_returns_metadata(
    chat_service: ChatService,
) -> None:
    """
    It should build assistant response metadata.
    """

    response = build_agent_response(
        usage=build_token_usage(),
    )

    metadata = chat_service._build_response_metadata(
        response,
    )

    assert metadata == {
        "provider": response.provider,
        "model": response.model,
        "finish_reason": response.finish_reason,
        "latency_ms": response.latency_ms,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        },
        **response.metadata,
    }
