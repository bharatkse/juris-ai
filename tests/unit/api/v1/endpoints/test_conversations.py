"""
Unit tests for conversation API endpoints.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

from src.api.v1.endpoints.conversations import (
    archive_conversation,
    create_conversation,
    get_conversation,
)
from src.core.response import ApiResponse
from tests.builders.schemas import build_create_conversation_request
from tests.factories.conversation import ConversationFactory


@pytest.mark.asyncio
@patch("src.api.v1.endpoints.conversations.ConversationResponse.model_validate")
async def test_create_conversation(
    mock_model_validate: MagicMock,
) -> None:
    """
    It should create a conversation.
    """

    conversation = ConversationFactory.build()

    request = build_create_conversation_request()

    response_model = MagicMock()

    mock_model_validate.return_value = response_model

    service = MagicMock()
    service.create = AsyncMock(
        return_value=conversation,
    )

    response = await create_conversation(
        request=request,
        service=service,
    )

    assert isinstance(
        response,
        ApiResponse,
    )

    assert response.status_code == status.HTTP_201_CREATED

    service.create.assert_awaited_once_with(
        request,
    )

    mock_model_validate.assert_called_once_with(
        conversation,
        from_attributes=True,
    )


@pytest.mark.asyncio
@patch("src.api.v1.endpoints.conversations.ConversationResponse.model_validate")
async def test_get_conversation(
    mock_model_validate: MagicMock,
) -> None:
    """
    It should return a conversation.
    """

    conversation = ConversationFactory.build()

    response_model = MagicMock()

    mock_model_validate.return_value = response_model

    service = MagicMock()
    service.get = AsyncMock(
        return_value=conversation,
    )

    response = await get_conversation(
        conversation_id=conversation.id,
        service=service,
    )

    assert isinstance(
        response,
        ApiResponse,
    )

    assert response.status_code == status.HTTP_200_OK

    service.get.assert_awaited_once_with(
        conversation.id,
    )

    mock_model_validate.assert_called_once_with(
        conversation,
        from_attributes=True,
    )


@pytest.mark.asyncio
async def test_get_conversation_raises_when_not_found() -> None:
    """
    It should raise when the conversation does not exist.
    """

    service = MagicMock()
    service.get = AsyncMock(
        return_value=None,
    )

    with pytest.raises(
        HTTPException,
    ) as exc:
        await get_conversation(
            conversation_id="conv_1234567890abcdef1234567890abcdef",
            service=service,
        )

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc.value.detail == "Conversation not found."

    service.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_archive_conversation() -> None:
    """
    It should archive a conversation.
    """

    conversation = ConversationFactory.build()

    service = MagicMock()
    service.get = AsyncMock(
        return_value=conversation,
    )
    service.archive = AsyncMock()

    response = await archive_conversation(
        conversation_id=conversation.id,
        service=service,
    )

    assert isinstance(
        response,
        ApiResponse,
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT

    service.get.assert_awaited_once_with(
        conversation.id,
    )

    service.archive.assert_awaited_once_with(
        conversation,
    )


@pytest.mark.asyncio
async def test_archive_conversation_raises_when_not_found() -> None:
    """
    It should raise when attempting to archive a missing conversation.
    """

    service = MagicMock()
    service.get = AsyncMock(
        return_value=None,
    )
    service.archive = AsyncMock()

    with pytest.raises(
        HTTPException,
    ) as exc:
        await archive_conversation(
            conversation_id="conv_1234567890abcdef1234567890abcdef",
            service=service,
        )

    assert exc.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc.value.detail == "Conversation not found."

    service.get.assert_awaited_once()
    service.archive.assert_not_awaited()
