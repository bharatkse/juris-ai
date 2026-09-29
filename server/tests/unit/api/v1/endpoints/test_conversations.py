"""
Unit tests for conversation API endpoints.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.routing import APIRoute

from api.dependencies.auth import get_current_user
from api.dependencies.conversation import get_conversation_service
from api.schemas.conversation import ConversationMessageResponse
from api.utilities.api_response import ApiResponse
from api.v1.endpoints.conversations import (
    archive_conversation,
    create_conversation,
    get_conversation,
    list_conversation_messages,
    router,
)
from core.exceptions.httpx import ConversationInactiveError
from core.exceptions.httpx import NotFoundError as ConversationNotFoundError
from tests.builders.api.schemas import build_create_conversation_request
from tests.unit.factories.conversation import ConversationFactory
from tests.unit.factories.conversation_event import ConversationEventFactory


@pytest.mark.asyncio
@patch(
    "api.v1.endpoints.conversations.ConversationResponse.model_validate",
)
async def test_create_conversation(
    mock_model_validate: MagicMock,
) -> None:
    """
    It should create a conversation.
    """

    conversation = ConversationFactory.build()
    request = build_create_conversation_request()

    current_user = MagicMock()
    current_user.id = conversation.user_id

    response_model = MagicMock()
    mock_model_validate.return_value = response_model

    service = MagicMock()
    service.create = AsyncMock(
        return_value=conversation,
    )

    response = await create_conversation(
        request=request,
        current_user=current_user,
        service=service,
    )

    assert isinstance(
        response,
        ApiResponse,
    )

    assert response.status_code == status.HTTP_201_CREATED

    service.create.assert_awaited_once()

    created_request = service.create.await_args.kwargs["request"]

    assert created_request.title == request.title

    mock_model_validate.assert_called_once_with(
        conversation,
        from_attributes=True,
    )


@pytest.mark.asyncio
@patch(
    "api.v1.endpoints.conversations.ConversationResponse.model_validate",
)
async def test_get_conversation(
    mock_model_validate: MagicMock,
) -> None:
    """
    It should return a conversation.
    """

    conversation = ConversationFactory.build()

    current_user = MagicMock()
    current_user.id = conversation.user_id

    response_model = MagicMock()
    mock_model_validate.return_value = response_model

    service = MagicMock()
    service.get_or_raise = AsyncMock(
        return_value=conversation,
    )

    response = await get_conversation(
        conversation_id=conversation.id,
        current_user=current_user,
        service=service,
    )

    assert isinstance(
        response,
        ApiResponse,
    )

    assert response.status_code == status.HTTP_200_OK

    service.get_or_raise.assert_awaited_once_with(
        conversation_id=conversation.id,
        user_id=current_user.id,
    )

    mock_model_validate.assert_called_once_with(
        conversation,
        from_attributes=True,
    )


@pytest.mark.asyncio
async def test_get_conversation_raises_when_not_found() -> None:
    """
    It should propagate when the conversation does not exist.
    """

    conversation_id = "conv_1234567890abcdef1234567890abcdef"

    current_user = MagicMock()
    current_user.id = "user_1234567890abcdef1234567890abcdef"

    service = MagicMock()
    service.get_or_raise = AsyncMock(
        side_effect=ConversationNotFoundError(
            message="Conversation not found.",
        ),
    )

    with pytest.raises(
        ConversationNotFoundError,
    ):
        await get_conversation(
            conversation_id=conversation_id,
            current_user=current_user,
            service=service,
        )

    service.get_or_raise.assert_awaited_once_with(
        conversation_id=conversation_id,
        user_id=current_user.id,
    )


@pytest.mark.asyncio
async def test_archive_conversation() -> None:
    """
    It should archive a conversation.
    """

    conversation = ConversationFactory.build()

    current_user = MagicMock()
    current_user.id = conversation.user_id

    service = MagicMock()
    service.archive = AsyncMock(
        return_value=conversation,
    )

    response = await archive_conversation(
        conversation_id=conversation.id,
        current_user=current_user,
        service=service,
    )

    assert isinstance(
        response,
        ApiResponse,
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    service.archive.assert_awaited_once_with(
        conversation_id=conversation.id,
        user_id=current_user.id,
    )


@pytest.mark.asyncio
async def test_archive_conversation_raises_when_not_found() -> None:
    """
    It should propagate when attempting to archive a missing conversation.
    """

    conversation_id = "conv_1234567890abcdef1234567890abcdef"

    current_user = MagicMock()
    current_user.id = "user_1234567890abcdef1234567890abcdef"

    service = MagicMock()
    service.archive = AsyncMock(
        side_effect=ConversationNotFoundError(
            message="Conversation not found.",
        ),
    )

    with pytest.raises(
        ConversationNotFoundError,
    ):
        await archive_conversation(
            conversation_id=conversation_id,
            current_user=current_user,
            service=service,
        )

    service.archive.assert_awaited_once_with(
        conversation_id=conversation_id,
        user_id=current_user.id,
    )


def _message_services(
    *,
    events: list | None = None,
    total: int = 0,
    get_or_raise: AsyncMock | None = None,
) -> tuple[MagicMock, MagicMock]:
    service = MagicMock()
    service.get_or_raise = get_or_raise or AsyncMock()

    event_service = MagicMock()
    event_service.list_page = AsyncMock(
        return_value=(events or [], total),
    )

    return service, event_service


@pytest.mark.asyncio
async def test_list_conversation_messages_checks_ownership_then_lists() -> None:
    """
    It should check the caller owns the conversation, then return that
    conversation's page of messages.
    """

    conversation = ConversationFactory.build()

    current_user = MagicMock()
    current_user.id = conversation.user_id

    user_event = ConversationEventFactory.build(
        conversation=conversation,
        user_message=True,
        content="Send the summary.",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    resumed_event = ConversationEventFactory.build(
        conversation=conversation,
        assistant_message=True,
        parent_event_id=user_event.id,
        content="Sent.",
        event_metadata={"resumed_agent_action_id": "actn_1"},
        created_at=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
    )

    service, event_service = _message_services(
        events=[user_event, resumed_event],
        total=3,
    )

    response = await list_conversation_messages(
        conversation_id=conversation.id,
        offset=0,
        limit=2,
        current_user=current_user,
        service=service,
        event_service=event_service,
    )

    service.get_or_raise.assert_awaited_once_with(
        conversation_id=conversation.id,
        user_id=current_user.id,
    )
    event_service.list_page.assert_awaited_once_with(
        conversation_id=conversation.id,
        offset=0,
        limit=2,
    )

    assert response.status_code == status.HTTP_200_OK

    page = json.loads(response.body)["data"]

    assert page["pagination"] == {
        "total": 3,
        "offset": 0,
        "limit": 2,
        "has_more": True,
    }
    assert [item["content"] for item in page["items"]] == ["Send the summary.", "Sent."]
    assert page["items"][1] == {
        "id": resumed_event.id,
        "conversation_id": conversation.id,
        "parent_event_id": user_event.id,
        "role": "assistant",
        "content": "Sent.",
        "metadata": {"resumed_agent_action_id": "actn_1"},
        "citations": [],
        "sources": [],
        "created_at": "2026-01-01T00:01:00Z",
    }


@pytest.mark.parametrize(
    "error",
    [
        ConversationNotFoundError(message="Conversation not found."),
        ConversationInactiveError(),
    ],
)
@pytest.mark.asyncio
async def test_list_conversation_messages_never_lists_when_ownership_fails(
    error: Exception,
) -> None:
    """
    Another user's (not found) or an archived conversation should fail
    the same way GET /conversations/{id} does, before any message is read.
    """

    current_user = MagicMock()
    current_user.id = "user_1234567890abcdef1234567890abcdef"

    service, event_service = _message_services(
        get_or_raise=AsyncMock(side_effect=error),
    )

    with pytest.raises(type(error)):
        await list_conversation_messages(
            conversation_id="conv_1234567890abcdef1234567890abcdef",
            offset=0,
            limit=20,
            current_user=current_user,
            service=service,
            event_service=event_service,
        )

    event_service.list_page.assert_not_awaited()


def test_messages_route_uses_the_same_ownership_dependency_as_get() -> None:
    """
    The messages route should authorize through the same
    ConversationService dependency as GET /conversations/{id}, and bound
    its page size like the other paginated lists.
    """

    routes = {
        (route.path, method): route
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }

    get_route = routes[("/conversations/{conversation_id}", "GET")]
    messages_route = routes[("/conversations/{conversation_id}/messages", "GET")]

    def _calls(route: APIRoute) -> set:
        return {dependency.call for dependency in route.dependant.dependencies}

    assert {get_current_user, get_conversation_service} <= _calls(get_route)
    assert {get_current_user, get_conversation_service} <= _calls(messages_route)

    limit = next(param for param in messages_route.dependant.query_params if param.name == "limit")
    offset = next(
        param for param in messages_route.dependant.query_params if param.name == "offset"
    )

    assert {type(meta).__name__ for meta in limit.field_info.metadata} >= {"Ge", "Le"}
    assert {type(meta).__name__ for meta in offset.field_info.metadata} >= {"Ge"}


def test_message_response_splits_stored_citations_and_sources() -> None:
    """
    The event's citations column holds {"citations": [...], "sources":
    [...]}; the response should expose both lists, and empty lists when
    nothing was stored.
    """

    cited = ConversationEventFactory.build(
        assistant_message=True,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        citations={
            "citations": [{"title": "IT Act 2000", "source": "retriever", "page": 4}],
            "sources": [{"title": "IT Act 2000", "uri": None, "type": "act"}],
        },
    )
    plain = ConversationEventFactory.build(
        user_message=True,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        event_metadata=None,
        citations=None,
    )

    cited_response = ConversationMessageResponse.from_event(cited)
    plain_response = ConversationMessageResponse.from_event(plain)

    assert cited_response.citations[0].title == "IT Act 2000"
    assert cited_response.citations[0].page == 4
    assert cited_response.sources[0].type == "act"

    assert plain_response.citations == []
    assert plain_response.sources == []
    assert plain_response.metadata == {}
