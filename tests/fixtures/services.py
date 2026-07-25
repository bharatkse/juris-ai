"""
Service fixtures.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.chat import ChatService
from src.services.conversation import ConversationService
from src.services.user import UserService


@pytest.fixture
def user_service(
    mock_async_session: AsyncMock,
    mock_user_repository: MagicMock,
    mock_password_service: MagicMock,
) -> UserService:
    """
    Create a user service.
    """

    return UserService(
        session=mock_async_session,
        repository=mock_user_repository,
        password_service=mock_password_service,
    )


@pytest.fixture
def conversation_service(
    mock_async_session: AsyncMock,
    mock_conversation_repository: MagicMock,
    mock_user_repository: MagicMock,
) -> ConversationService:
    """
    Return a conversation service.
    """

    return ConversationService(
        session=mock_async_session,
        repository=mock_conversation_repository,
        user_repository=mock_user_repository,
    )


@pytest.fixture
def chat_service(
    mock_async_session: AsyncMock,
    mock_conversation_repository: MagicMock,
    mock_conversation_event_repository: MagicMock,
    mock_agent: MagicMock,
) -> ChatService:
    """
    Return a chat service.
    """

    return ChatService(
        session=mock_async_session,
        conversation_repository=mock_conversation_repository,
        event_repository=mock_conversation_event_repository,
        agent=mock_agent,
    )
