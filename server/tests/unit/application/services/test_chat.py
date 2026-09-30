"""
Unit tests for ChatService.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from agentic.guardrails.schemas import GuardrailActionEnum
from agentic.orchestration.schemas.request import OrchestratorRequest
from agentic.orchestration.schemas.response import (
    ApprovalResponse,
    Citation,
    GuardrailInfo,
    Source,
)
from application.services import chat as chat_module
from application.services.chat import ChatService
from application.services.conversation_summarization import UNSUMMARIZED_EVENT_LIMIT
from application.services.internal_dto.chat import ChatResultDTO
from application.services.internal_dto.stream import ChatStreamChunkDTO
from core.dto.tool import ToolFileDTO
from core.enums import ApprovalStatusEnum, MessageRoleEnum
from core.exceptions.httpx import ConversationInactiveError, NotFoundError
from tests.builders.agentic.orchestrator import build_orchestrator_response
from tests.unit.factories.conversation import ConversationFactory
from tests.unit.factories.conversation_event import ConversationEventFactory
from tests.unit.helpers.identifiers import unknown_conversation_id, unknown_user_id

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
    assert orchestration_request.attachments == ()

    mock_conversation_event_service.create.assert_any_await(
        conversation_id=conversation.id,
        request_id=request_id,
        parent_event_id=user_event.id,
        role=MessageRoleEnum.ASSISTANT,
        content=response.content,
        metadata=response.metadata.model_dump(
            mode="json",
        ),
        citations=None,
    )

    chat_service.commit.assert_awaited_once_with()
    chat_service.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_passes_uploaded_files_to_orchestrator(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    """
    Uploaded files should reach the orchestrator request unchanged.

    Regression: OrchestratorRequest.attachments was typed
    list[Attachment], so any chat with a file failed validation.
    """

    conversation = ConversationFactory.build()
    request_id = uuid4()
    upload = ToolFileDTO(filename="contract.txt", content=b"terms", content_type="text/plain")

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        request_id=request_id,
        role=MessageRoleEnum.USER,
        content="Hello",
    )
    response = build_orchestrator_response(conversation_id=conversation.id, content="Hi")
    assistant_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        request_id=request_id,
        parent_event_id=user_event.id,
        role=MessageRoleEnum.ASSISTANT,
        content=response.content,
        event_metadata=response.metadata.model_dump(mode="json"),
    )

    mock_conversation_service.get_or_raise = AsyncMock(return_value=conversation)
    mock_conversation_event_service.create = AsyncMock(side_effect=[user_event, assistant_event])
    mock_conversation_event_service.list = AsyncMock(return_value=[])
    mock_orchestrator.handle = AsyncMock(return_value=response)
    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    await chat_service.chat(
        user_id=conversation.user_id,
        conversation_id=conversation.id,
        message="Hello",
        request_id=request_id,
        files=(upload,),
    )

    orchestration_request = mock_orchestrator.handle.await_args.kwargs["request"]

    assert orchestration_request.attachments == (upload,)


@pytest.mark.asyncio
async def test_chat_persists_citations_and_sources_when_present(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    """
    An answer carrying citations/sources should have them persisted
    onto the assistant conversation_event's ``citations`` column, so a
    reopened conversation can show what backed a prior answer.
    """

    conversation = ConversationFactory.build()
    request_id = uuid4()

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        request_id=request_id,
        role=MessageRoleEnum.USER,
        content=TEST_MESSAGE,
    )

    citation = Citation(
        title="IT Act 2000, Section 43A",
        source="it-act-2000",
        reference="s.43A",
        snippet="Compensation for failure to protect data.",
    )
    source = Source(
        title="Information Technology Act, 2000",
        uri="https://example.test/it-act-2000",
        type="statute",
    )

    response = build_orchestrator_response(
        conversation_id=conversation.id,
        content="Answer with citations.",
        citations=[citation],
        sources=[source],
    )

    assistant_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        request_id=request_id,
        parent_event_id=user_event.id,
        role=MessageRoleEnum.ASSISTANT,
        content=response.content,
    )

    mock_conversation_service.get_or_raise = AsyncMock(
        return_value=conversation,
    )

    mock_conversation_event_service.create = AsyncMock(
        side_effect=[user_event, assistant_event],
    )

    mock_conversation_event_service.list = AsyncMock(
        return_value=[],
    )

    mock_orchestrator.handle = AsyncMock(
        return_value=response,
    )

    chat_service.commit = AsyncMock()

    await chat_service.chat(
        user_id=conversation.user_id,
        conversation_id=conversation.id,
        message=TEST_MESSAGE,
        request_id=request_id,
    )

    mock_conversation_event_service.create.assert_any_await(
        conversation_id=conversation.id,
        request_id=request_id,
        parent_event_id=user_event.id,
        role=MessageRoleEnum.ASSISTANT,
        content=response.content,
        metadata=response.metadata.model_dump(
            mode="json",
        ),
        citations={
            "citations": [citation.model_dump(mode="json")],
            "sources": [source.model_dump(mode="json")],
        },
    )


@pytest.mark.asyncio
async def test_chat_records_compliance_log_entries(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
    mock_compliance_log_service: MagicMock,
) -> None:
    """
    A successful chat turn must record both a REQUEST_RECEIVED and a
    RESPONSE_RETURNED compliance log entry -- the "who asked/what was
    returned" halves of the audit trail (application/services/
    compliance_log.py).
    """

    conversation = ConversationFactory.build()
    request_id = uuid4()

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        request_id=request_id,
        role=MessageRoleEnum.USER,
        content=TEST_MESSAGE,
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
    )

    mock_conversation_service.get_or_raise = AsyncMock(return_value=conversation)
    mock_conversation_event_service.create = AsyncMock(
        side_effect=[user_event, assistant_event],
    )
    mock_conversation_event_service.list = AsyncMock(return_value=[])
    mock_orchestrator.handle = AsyncMock(return_value=response)
    chat_service.commit = AsyncMock()

    await chat_service.chat(
        user_id=conversation.user_id,
        conversation_id=conversation.id,
        message=TEST_MESSAGE,
        request_id=request_id,
    )

    mock_compliance_log_service.record_request_received.assert_awaited_once_with(
        request_id=request_id,
        user_id=str(conversation.user_id),
        tenant_id=str(conversation.user_id),
        conversation_id=str(conversation.id),
        conversation_event_id=str(user_event.id),
        message=TEST_MESSAGE,
    )

    mock_compliance_log_service.record_response_returned.assert_awaited_once_with(
        request_id=request_id,
        user_id=str(conversation.user_id),
        tenant_id=str(conversation.user_id),
        conversation_id=str(conversation.id),
        conversation_event_id=str(assistant_event.id),
        content=response.content,
        citation_count=0,
        action_required=False,
    )

    # Both compliance writes must happen strictly inside the same
    # transaction as the conversation-event writes -- before commit(),
    # never after.
    chat_service.commit.assert_awaited_once_with()


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
        limit=UNSUMMARIZED_EVENT_LIMIT,
    )

    mock_orchestrator.stream.assert_called_once()

    chat_service.rollback.assert_awaited_once()
    chat_service.commit.assert_not_awaited()


def _fake_stream(chunks: list[ChatStreamChunkDTO]):
    """
    Build a callable matching AIOrchestrator.stream()'s real shape: a
    plain (non-async) method that returns an async generator, called
    with request=/action_workflow_service= kwargs and iterated via
    ``async for`` -- not awaited itself. mock_orchestrator.stream is a
    bare MagicMock (see tests/unit/fixtures/agentic/orchestrator.py),
    not an AsyncMock, precisely so it can be given this shape.
    """

    async def _generator(**_kwargs):
        for chunk in chunks:
            yield chunk

    return _generator


@pytest.mark.asyncio
async def test_stream_chat_yields_every_chunk_and_persists_the_final_response(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
    mock_compliance_log_service: MagicMock,
    mock_usage_service: MagicMock,
) -> None:
    """
    Regression test for the two bugs found in stream_chat(): it read
    chunk.is_complete (the DTO field is is_final) and typed
    final_response as AgentResponseDTO (the DTO's response field is
    actually OrchestratorResponse) -- both would have raised or
    silently never matched on the very first real chunk, which is
    exactly why no earlier test caught this: none of the existing
    stream_chat() tests ever iterated a real chunk sequence through to
    a final one.

    Also the core parity assertion for this fix: a successful stream
    must persist the assistant event, log both compliance entries, and
    record usage -- exactly like chat() -- not just yield chunks
    through to the caller.
    """

    conversation = ConversationFactory.build()
    request_id = _request_id()

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        request_id=request_id,
        role=MessageRoleEnum.USER,
        content=TEST_MESSAGE,
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
    )

    mock_conversation_service.get_or_raise = AsyncMock(return_value=conversation)
    mock_conversation_event_service.create = AsyncMock(
        side_effect=[user_event, assistant_event],
    )
    mock_conversation_event_service.list = AsyncMock(return_value=[])

    chunks = [
        ChatStreamChunkDTO(content="Hello ", is_final=False),
        ChatStreamChunkDTO(content="world!", is_final=False),
        ChatStreamChunkDTO(content="", is_final=True, response=response),
    ]

    async def stream(**_kwargs):
        _spend(response.usage.prompt_tokens, response.usage.completion_tokens)
        for chunk in chunks:
            yield chunk

    mock_orchestrator.stream = stream

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    received = [
        chunk
        async for chunk in chat_service.stream_chat(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
            request_id=request_id,
        )
    ]

    # Every chunk reaches the caller, in order -- streaming itself
    # isn't swallowed by the persistence tail.
    assert received == chunks

    mock_conversation_event_service.create.assert_any_await(
        conversation_id=conversation.id,
        request_id=request_id,
        parent_event_id=user_event.id,
        role=MessageRoleEnum.ASSISTANT,
        content=response.content,
        metadata=response.metadata.model_dump(mode="json"),
        citations=None,
    )

    mock_compliance_log_service.record_request_received.assert_awaited_once_with(
        request_id=request_id,
        user_id=str(conversation.user_id),
        tenant_id=str(conversation.user_id),
        conversation_id=str(conversation.id),
        conversation_event_id=str(user_event.id),
        message=TEST_MESSAGE,
    )

    mock_compliance_log_service.record_response_returned.assert_awaited_once_with(
        request_id=request_id,
        user_id=str(conversation.user_id),
        tenant_id=str(conversation.user_id),
        conversation_id=str(conversation.id),
        conversation_event_id=str(assistant_event.id),
        content=response.content,
        citation_count=0,
        action_required=False,
    )

    assert _recorded(mock_usage_service) == (
        str(conversation.user_id),
        str(request_id),
        response.usage.prompt_tokens,
        response.usage.completion_tokens,
    )

    chat_service.commit.assert_awaited_once_with()
    chat_service.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_chat_merges_approval_and_guardrail_into_assistant_event_metadata(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    """
    chat() merges both result.approval and result.guardrail into the
    persisted assistant event's metadata; stream_chat() previously
    merged neither (approval) or hadn't been touched at all
    (guardrail, added in this same fix). Both must reach parity
    through the shared _persist_assistant_response() helper.
    """

    conversation = ConversationFactory.build()
    request_id = _request_id()

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        request_id=request_id,
        role=MessageRoleEnum.USER,
        content=TEST_MESSAGE,
    )

    approval = ApprovalResponse(
        approval_id="apvl_test",
        status=ApprovalStatusEnum.WAITING,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    guardrail = GuardrailInfo(
        action=GuardrailActionEnum.REDACTED,
        detection_count=1,
        categories=["PII"],
    )

    response = build_orchestrator_response(
        conversation_id=conversation.id,
        content="Redacted answer.",
    )
    response = response.model_copy(
        update={
            "approval": approval,
            "guardrail": guardrail,
        },
    )

    assistant_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        request_id=request_id,
        parent_event_id=user_event.id,
        role=MessageRoleEnum.ASSISTANT,
        content=response.content,
    )

    mock_conversation_service.get_or_raise = AsyncMock(return_value=conversation)
    mock_conversation_event_service.create = AsyncMock(
        side_effect=[user_event, assistant_event],
    )
    mock_conversation_event_service.list = AsyncMock(return_value=[])

    chunks = [
        ChatStreamChunkDTO(content="Redacted answer.", is_final=True, response=response),
    ]
    mock_orchestrator.stream = MagicMock(side_effect=_fake_stream(chunks))

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    async for _ in chat_service.stream_chat(
        user_id=conversation.user_id,
        conversation_id=conversation.id,
        message=TEST_MESSAGE,
        request_id=request_id,
    ):
        pass

    expected_metadata = response.metadata.model_dump(mode="json")
    expected_metadata["approval"] = approval.model_dump(mode="json")
    expected_metadata["guardrail"] = guardrail.model_dump(mode="json")

    mock_conversation_event_service.create.assert_any_await(
        conversation_id=conversation.id,
        request_id=request_id,
        parent_event_id=user_event.id,
        role=MessageRoleEnum.ASSISTANT,
        content=response.content,
        metadata=expected_metadata,
        citations=None,
    )


@pytest.mark.asyncio
async def test_stream_chat_raises_when_the_stream_never_yields_a_final_chunk(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> None:
    """
    A stream that ends without ever yielding is_final=True must raise
    rather than silently return -- there is no response to persist.
    """

    conversation = ConversationFactory.build()
    request_id = _request_id()

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
        request_id=request_id,
        role=MessageRoleEnum.USER,
        content=TEST_MESSAGE,
    )

    mock_conversation_service.get_or_raise = AsyncMock(return_value=conversation)
    mock_conversation_event_service.create = AsyncMock(return_value=user_event)
    mock_conversation_event_service.list = AsyncMock(return_value=[])

    chunks = [ChatStreamChunkDTO(content="incomplete", is_final=False)]
    mock_orchestrator.stream = MagicMock(side_effect=_fake_stream(chunks))

    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()

    with pytest.raises(RuntimeError, match="without a final response"):
        async for _ in chat_service.stream_chat(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
            request_id=request_id,
        ):
            pass

    chat_service.rollback.assert_awaited_once()
    chat_service.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# Per-request token quota (review R3)
# ---------------------------------------------------------------------------


def _spend(prompt_tokens: int = 700, completion_tokens: int = 200) -> None:
    """Make LLM calls worth these tokens, counted the real way (a usage scope)."""

    from core.usage import record_llm_usage, usage_scope

    with usage_scope():
        record_llm_usage(
            provider="groq",
            model="test",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )


def _recorded(mock_usage_service: MagicMock) -> tuple[str, str, int, int]:
    """(user_id, request_id, input, output) of the one usage record."""

    mock_usage_service.record.assert_awaited_once()
    kwargs = mock_usage_service.record.await_args.kwargs
    return (
        kwargs["user_id"],
        kwargs["request_id"],
        kwargs["input_tokens"],
        kwargs["output_tokens"],
    )


def _quota_refusal():
    from core.exceptions.rate_limit import RequestTokenQuotaExceededError

    return RequestTokenQuotaExceededError(
        quota=1000,
        used=900,
        requested=400,
        prompt_tokens=700,
        completion_tokens=200,
    )


def _arrange_chat(mock_conversation_service, mock_conversation_event_service):
    conversation = ConversationFactory.build()
    mock_conversation_service.get_or_raise = AsyncMock(return_value=conversation)
    mock_conversation_event_service.create = AsyncMock(
        return_value=ConversationEventFactory.build(
            conversation_id=conversation.id,
            role=MessageRoleEnum.USER,
            content=TEST_MESSAGE,
        ),
    )
    mock_conversation_event_service.list = AsyncMock(return_value=[])
    return conversation


@pytest.mark.asyncio
async def test_chat_runs_the_orchestrator_under_the_request_token_quota(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
    mock_usage_service: MagicMock,
) -> None:
    from core.usage import usage_scope

    conversation = _arrange_chat(mock_conversation_service, mock_conversation_event_service)
    mock_usage_service.request_token_quota = MagicMock(return_value=4321)
    quotas: list[int | None] = []

    async def handle(**_kwargs):
        with usage_scope() as meter:
            quotas.append(meter.quota)
        _spend(300, 50)
        raise SQLAlchemyError("stop here")

    mock_orchestrator.handle = handle
    chat_service.rollback = AsyncMock()
    request_id = _request_id()

    with pytest.raises(SQLAlchemyError):
        await chat_service.chat(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
            request_id=request_id,
        )

    assert quotas == [4321]
    # R19: a request that fails after its LLM calls still records them.
    assert _recorded(mock_usage_service) == (
        str(conversation.user_id),
        str(request_id),
        300,
        50,
    )

    with usage_scope() as after:
        pass
    assert after.quota is None


@pytest.mark.asyncio
async def test_chat_records_the_usage_of_a_request_the_quota_refused(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
    mock_usage_service: MagicMock,
) -> None:
    from core.exceptions.rate_limit import RequestTokenQuotaExceededError

    conversation = _arrange_chat(mock_conversation_service, mock_conversation_event_service)

    async def handle(**_kwargs):
        _spend(700, 200)
        raise _quota_refusal()

    mock_orchestrator.handle = handle
    chat_service.commit = AsyncMock()
    chat_service.rollback = AsyncMock()
    request_id = _request_id()

    with (
        patch.object(chat_module.metrics, "record_token_quota_rejection") as rejected,
        pytest.raises(RequestTokenQuotaExceededError),
    ):
        await chat_service.chat(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
            request_id=request_id,
        )

    rejected.assert_called_once_with(quota="per_request")
    chat_service.rollback.assert_awaited_once()
    chat_service.commit.assert_not_awaited()
    assert _recorded(mock_usage_service) == (
        str(conversation.user_id),
        str(request_id),
        700,
        200,
    )


@pytest.mark.asyncio
async def test_stream_chat_records_the_usage_of_a_request_the_quota_refused(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
    mock_usage_service: MagicMock,
) -> None:
    from core.exceptions.rate_limit import RequestTokenQuotaExceededError
    from core.usage import usage_scope

    conversation = _arrange_chat(mock_conversation_service, mock_conversation_event_service)
    mock_usage_service.request_token_quota = MagicMock(return_value=1000)
    quotas: list[int | None] = []

    async def stream(**_kwargs):
        with usage_scope() as meter:
            quotas.append(meter.quota)
        _spend(700, 200)
        raise _quota_refusal()
        yield  # pragma: no cover -- makes this an async generator

    mock_orchestrator.stream = stream
    chat_service.rollback = AsyncMock()
    request_id = _request_id()

    with (
        patch.object(chat_module.metrics, "record_token_quota_rejection") as rejected,
        pytest.raises(RequestTokenQuotaExceededError),
    ):
        async for _ in chat_service.stream_chat(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
            request_id=request_id,
        ):
            pass

    rejected.assert_called_once_with(quota="per_request")
    assert quotas == [1000]
    assert _recorded(mock_usage_service) == (
        str(conversation.user_id),
        str(request_id),
        700,
        200,
    )


@pytest.mark.asyncio
async def test_a_stream_cancelled_mid_run_records_its_usage(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
    mock_usage_service: MagicMock,
) -> None:
    """
    R19: the client disconnects while the orchestrator is still working
    (the request task is cancelled). The tokens spent so far are recorded
    once, and the cancellation still propagates.
    """

    conversation = _arrange_chat(mock_conversation_service, mock_conversation_event_service)
    working = asyncio.Event()

    async def stream(**_kwargs):
        from core.usage import record_llm_usage, usage_scope

        with usage_scope():
            record_llm_usage(
                provider="groq",
                model="test",
                prompt_tokens=400,
                completion_tokens=40,
                total_tokens=440,
            )
            working.set()
            await asyncio.Event().wait()  # the next LLM call never returns
        yield  # pragma: no cover

    mock_orchestrator.stream = stream
    chat_service.rollback = AsyncMock()
    request_id = _request_id()

    async def consume() -> None:
        async for _ in chat_service.stream_chat(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            message=TEST_MESSAGE,
            request_id=request_id,
        ):
            pass

    task = asyncio.create_task(consume())
    await working.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert _recorded(mock_usage_service) == (
        str(conversation.user_id),
        str(request_id),
        400,
        40,
    )


@pytest.mark.asyncio
async def test_a_stream_closed_between_chunks_records_its_usage(
    chat_service: ChatService,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
    mock_usage_service: MagicMock,
) -> None:
    """
    R19: the client goes away after the first chunk; the stream is closed
    while suspended at a yield (aclose). Recorded once, with the tokens the
    orchestrator's scope counted before it was closed.
    """

    conversation = _arrange_chat(mock_conversation_service, mock_conversation_event_service)

    async def stream(**_kwargs):
        from core.usage import record_llm_usage, usage_scope

        with usage_scope():
            record_llm_usage(
                provider="groq",
                model="test",
                prompt_tokens=900,
                completion_tokens=90,
                total_tokens=990,
            )
            yield ChatStreamChunkDTO(content="Hello ", is_final=False)
            yield ChatStreamChunkDTO(content="world", is_final=False)  # pragma: no cover

    mock_orchestrator.stream = stream
    chat_service.rollback = AsyncMock()
    request_id = _request_id()

    chunks = chat_service.stream_chat(
        user_id=conversation.user_id,
        conversation_id=conversation.id,
        message=TEST_MESSAGE,
        request_id=request_id,
    )
    await anext(chunks)
    await chunks.aclose()

    assert _recorded(mock_usage_service) == (
        str(conversation.user_id),
        str(request_id),
        900,
        90,
    )
