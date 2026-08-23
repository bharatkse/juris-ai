"""
Service fixtures.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.auth import AuthenticationService
from src.services.chat import ChatService
from src.services.conversation import ConversationService
from src.services.conversation_event import ConversationEventService
from src.services.document import DocumentService
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
) -> ConversationService:
    """
    Return a conversation service.
    """

    return ConversationService(
        session=mock_async_session,
        repository=mock_conversation_repository,
    )


@pytest.fixture
def chat_service(
    mock_async_session: AsyncMock,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
) -> ChatService:
    """
    Return a chat service.
    """

    return ChatService(
        session=mock_async_session,
        conversation_service=mock_conversation_service,
        conversation_event_service=mock_conversation_event_service,
        orchestrator=mock_orchestrator,
    )


@pytest.fixture
def document_service(
    mock_async_session: AsyncMock,
    mock_document_repository: MagicMock,
    mock_storage_client: MagicMock,
) -> DocumentService:
    """
    Return a document service.
    """

    return DocumentService(
        session=mock_async_session,
        repository=mock_document_repository,
        storage=mock_storage_client,
    )


@pytest.fixture
def authentication_service(
    mock_user_repository: MagicMock,
    mock_password_service: MagicMock,
) -> AuthenticationService:
    return AuthenticationService(
        user_repository=mock_user_repository,
        password_service=mock_password_service,
    )


@pytest.fixture
def mock_conversation_service() -> MagicMock:
    """
    Return a mocked conversation service.
    """

    return MagicMock(
        spec=ConversationService,
    )


@pytest.fixture
def mock_conversation_event_service() -> MagicMock:
    """
    Return a mocked conversation event service.
    """

    return MagicMock(
        spec=ConversationEventService,
    )


@pytest.fixture
def mock_password_service() -> MagicMock:
    """
    Provide a mocked PasswordService.
    """

    service = MagicMock()
    service.verify_password = MagicMock()

    return service
