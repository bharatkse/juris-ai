"""
Unit tests for conversation API endpoints.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from api.schemas.conversation import UpdateConversationRequest
from api.utilities.api_response import ApiResponse
from api.v1.endpoints.conversations import (
    archive_conversation,
    create_conversation,
    get_conversation,
    list_conversation_events,
    update_conversation,
)
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
async def test_update_conversation_title() -> None:
    """
    It should rename an authenticated user's conversation.
    """

    conversation = ConversationFactory.build(
        title="Updated title",
    )
    current_user = MagicMock()
    current_user.id = conversation.user_id
    service = MagicMock()
    service.update_title = AsyncMock(
        return_value=conversation,
    )

    response = await update_conversation(
        conversation_id=conversation.id,
        request=UpdateConversationRequest(title="Updated title"),
        current_user=current_user,
        service=service,
    )

    assert response.status_code == status.HTTP_200_OK
    service.update_title.assert_awaited_once_with(
        conversation_id=conversation.id,
        user_id=current_user.id,
        title="Updated title",
    )


@pytest.mark.asyncio
async def test_list_conversation_events_checks_owner_and_paginates() -> None:
    """
    It should return an owned conversation's chronological event page.
    """

    conversation = ConversationFactory.build()
    event = ConversationEventFactory.build(
        conversation=conversation,
        user_message=True,
    )
    current_user = MagicMock()
    current_user.id = conversation.user_id

    conversation_service = MagicMock()
    conversation_service.get_or_raise = AsyncMock(
        return_value=conversation,
    )
    event_service = MagicMock()
    event_service.list_page = AsyncMock(
        return_value=([event], 1),
    )

    response = await list_conversation_events(
        conversation_id=conversation.id,
        offset=0,
        limit=50,
        current_user=current_user,
        conversation_service=conversation_service,
        event_service=event_service,
    )
    payload = json.loads(response.body)

    assert payload["data"]["items"][0]["id"] == event.id
    assert payload["data"]["pagination"]["total"] == 1
    assert payload["data"]["pagination"]["has_more"] is False
    conversation_service.get_or_raise.assert_awaited_once_with(
        conversation_id=conversation.id,
        user_id=current_user.id,
    )
    event_service.list_page.assert_awaited_once_with(
        conversation_id=conversation.id,
        offset=0,
        limit=50,
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
