"""
Unit tests for chat API endpoints.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.responses import StreamingResponse

from api.dependencies.authorization import bind_document_acl
from api.schemas.chat import ChatStreamResponse, ConversationEventResponse
from api.utilities.api_response import ApiResponse
from api.v1.endpoints.chat import chat, stream_chat
from application.authorization.service import AuthorizationService
from application.context.request import bind_request_context
from tests.builders.api.schemas import build_chat_request
from tests.builders.application.chat import (
    build_chat_result,
    build_chat_stream_chunk,
)
from tests.helpers.identifiers import unknown_user_id
from tests.helpers.request import build_http_request


def _build_authorization_service() -> MagicMock:
    """
    Build an authorization service with a resolved document ACL.
    """

    authorization_service = MagicMock(
        spec=AuthorizationService,
    )

    authorization_service.get_allowed_document_ids.return_value = {
        "document-1",
        "document-2",
    }

    return authorization_service


async def _bind_test_acl(
    *,
    http_request,
    chat_request,
    current_user,
) -> MagicMock:
    """
    Bind request context and resolve the document ACL.

    Direct endpoint function calls bypass FastAPI's dependency injection,
    so the ACL dependency must be executed explicitly in unit tests.
    """

    authorization_service = _build_authorization_service()

    bind_request_context(
        request_id=http_request.state.context.request_id,
        conversation_id=str(chat_request.conversation_id),
    ).__enter__()

    await bind_document_acl(
        current_user=current_user,
        authorization_service=authorization_service,
    )

    return authorization_service


# def test_chat_route_binds_document_acl() -> None:
#     """
#     It should require ACL resolution before the chat route can run.
#     """

#     route = next(route for route in router.routes if getattr(route, "path", None) == "/chat")

#     stream_route = next(
#         route for route in router.routes if getattr(route, "path", None) == "/chat/stream"
#     )

#     route_dependencies = {dependency.call for dependency in route.dependent.dependencies}  # noqa: C416

#     stream_route_dependencies = {
#         dependency.call for dependency in stream_route.dependent.dependencies
#     }  # noqa: C416
#     assert bind_document_acl in route_dependencies
#     assert bind_document_acl in stream_route_dependencies


@pytest.mark.asyncio
@patch(
    "api.v1.endpoints.chat.ConversationEventResponse.model_validate",
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

    authorization_service = _build_authorization_service()

    with bind_request_context(
        request_id=http_request.state.context.request_id,
        conversation_id=str(request.conversation_id),
    ):
        await bind_document_acl(
            current_user=current_user,
            authorization_service=authorization_service,
        )

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
        files=(),
    )

    authorization_service.get_allowed_document_ids.assert_called_once_with(
        user_id=current_user.id,
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

    authorization_service = _build_authorization_service()

    with bind_request_context(
        request_id=http_request.state.context.request_id,
        conversation_id=str(request.conversation_id),
    ):
        await bind_document_acl(
            current_user=current_user,
            authorization_service=authorization_service,
        )

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

    authorization_service.get_allowed_document_ids.assert_called_once_with(
        user_id=current_user.id,
    )


@pytest.mark.asyncio
@patch("api.v1.endpoints.chat.encode_sse_event")
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

    authorization_service = _build_authorization_service()

    with bind_request_context(
        request_id=http_request.state.context.request_id,
        conversation_id=str(request.conversation_id),
    ):
        await bind_document_acl(
            current_user=current_user,
            authorization_service=authorization_service,
        )

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
        files=(),
    )

    authorization_service.get_allowed_document_ids.assert_called_once_with(
        user_id=current_user.id,
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
@patch("api.v1.endpoints.chat.logger")
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

    authorization_service = _build_authorization_service()

    with bind_request_context(
        request_id=http_request.state.context.request_id,
        conversation_id=str(request.conversation_id),
    ):
        await bind_document_acl(
            current_user=current_user,
            authorization_service=authorization_service,
        )

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

    authorization_service.get_allowed_document_ids.assert_called_once_with(
        user_id=current_user.id,
    )

    mock_logger.info.assert_any_call(
        "Client disconnected from chat stream.",
        extra={
            "operation": "stream_chat",
            "conversation_id": str(request.conversation_id),
            "user_id": str(current_user.id),
        },
    )
