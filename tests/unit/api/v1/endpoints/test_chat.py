"""
Unit tests for chat API endpoints.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.responses import StreamingResponse

from src.api.v1.endpoints.chat import chat, stream_chat
from src.core.response import ApiResponse
from src.schemas.chat import ChatStreamResponse, ConversationEventResponse
from tests.builders.chat import build_chat_result, build_chat_stream_chunk
from tests.builders.schemas import build_chat_request
from tests.helpers.identifiers import unknown_user_id
from tests.helpers.request import build_http_request


@pytest.mark.asyncio
@patch(
    "src.api.v1.endpoints.chat.ConversationEventResponse.model_validate",
    wraps=ConversationEventResponse.model_validate,
)
async def test_chat(
    mock_model_validate: MagicMock,
) -> None:
    """
    It should return a chat response.
    """

    result = build_chat_result()
    request = build_chat_request()

    current_user = MagicMock()
    current_user.id = result.conversation.user_id

    service = MagicMock()
    service.chat = AsyncMock(
        return_value=result,
    )

    http_request = build_http_request()

    response = await chat(
        http_request=http_request,
        chat_request=request,
        current_user=current_user,
        service=service,
    )

    assert isinstance(
        response,
        ApiResponse,
    )

    assert response.status_code == status.HTTP_200_OK

    service.chat.assert_awaited_once_with(
        user_id=current_user.id,
        conversation_id=request.conversation_id,
        message=request.message,
        request_id=http_request.state.context.request_id,
    )

    assert mock_model_validate.call_count == 2

    mock_model_validate.assert_any_call(
        result.user_event,
        from_attributes=True,
    )

    mock_model_validate.assert_any_call(
        result.assistant_event,
        from_attributes=True,
    )


@pytest.mark.asyncio
async def test_stream_chat_returns_streaming_response() -> None:
    """
    It should return a streaming response.
    """

    request = build_chat_request()

    current_user = MagicMock()
    current_user.id = "user_test"

    async def stream():
        yield build_chat_stream_chunk()

    service = MagicMock()
    service.stream_chat.return_value = stream()
    http_request = build_http_request()
    response = await stream_chat(
        http_request=http_request,
        chat_request=request,
        current_user=current_user,
        service=service,
    )

    assert isinstance(
        response,
        StreamingResponse,
    )

    assert response.media_type == "text/event-stream"

    assert response.headers["Cache-Control"] == "no-cache"
    assert response.headers["Connection"] == "keep-alive"
    assert response.headers["X-Accel-Buffering"] == "no"


@pytest.mark.asyncio
@patch("src.api.v1.endpoints.chat.encode_sse_event")
async def test_stream_chat_streams_events(
    mock_encode_sse_event: MagicMock,
) -> None:
    """
    It should encode streamed chat chunks as SSE events.
    """

    request = build_chat_request()

    current_user = MagicMock()
    current_user.id = "user_test"

    chunk = build_chat_stream_chunk()

    async def stream():
        yield chunk

    service = MagicMock()
    service.stream_chat.return_value = stream()
    http_request = build_http_request()
    mock_encode_sse_event.return_value = "data: test\n\n"

    response = await stream_chat(
        http_request=http_request,
        chat_request=request,
        current_user=current_user,
        service=service,
    )

    body = []

    async for item in response.body_iterator:
        body.append(item)

    assert body == ["data: test\n\n"]

    service.stream_chat.assert_called_once_with(
        user_id=current_user.id,
        conversation_id=request.conversation_id,
        message=request.message,
        request_id=http_request.state.context.request_id,
    )

    mock_encode_sse_event.assert_called_once()

    event = mock_encode_sse_event.call_args.args[0]

    assert isinstance(
        event,
        ChatStreamResponse,
    )

    assert event.content == chunk.content
    assert event.is_final == chunk.is_final
    assert event.metadata == chunk.metadata


@pytest.mark.asyncio
@patch("src.api.v1.endpoints.chat.logger")
async def test_stream_chat_propagates_cancelled_error(
    mock_logger: MagicMock,
) -> None:
    """
    It should log and propagate client disconnects.
    """

    request = build_chat_request()

    current_user = MagicMock()
    current_user.id = unknown_user_id()

    async def stream():
        raise asyncio.CancelledError
        yield

    service = MagicMock()
    service.stream_chat.return_value = stream()
    http_request = build_http_request()
    response = await stream_chat(
        http_request=http_request,
        chat_request=request,
        current_user=current_user,
        service=service,
    )

    with pytest.raises(
        asyncio.CancelledError,
    ):
        async for _ in response.body_iterator:
            pass

    mock_logger.info.assert_any_call(
        "Client disconnected from chat stream.",
        extra={
            "operation": "stream_chat",
            "conversation_id": str(request.conversation_id),
            "user_id": str(current_user.id),
        },
    )
