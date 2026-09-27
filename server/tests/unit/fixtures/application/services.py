"""
Service fixtures.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from application.services.auth import AuthenticationService
from application.services.chat import ChatService
from application.services.conversation import ConversationService
from application.services.conversation_event import ConversationEventService
from application.services.library import LibraryService
from application.services.user import UserService


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
def mock_action_workflow_service() -> MagicMock:
    service = MagicMock()

    service.prepare = AsyncMock()

    return service


@pytest.fixture
def mock_usage_service() -> MagicMock:
    service = MagicMock()

    service.record = AsyncMock()

    return service


@pytest.fixture
def mock_conversation_summarization_service() -> MagicMock:
    service = MagicMock()

    # Pass-through by default: no summarization side effects unless a
    # test explicitly overrides this.
    service.ensure_summarized = AsyncMock(side_effect=lambda *, conversation: conversation)

    return service


@pytest.fixture
def mock_compliance_log_service() -> MagicMock:
    service = MagicMock()

    service.record_request_received = AsyncMock()
    service.record_response_returned = AsyncMock()

    return service


@pytest.fixture
def chat_service(
    mock_async_session: AsyncMock,
    mock_conversation_service: MagicMock,
    mock_conversation_event_service: MagicMock,
    mock_orchestrator: MagicMock,
    mock_action_workflow_service: MagicMock,
    mock_usage_service: MagicMock,
    mock_conversation_summarization_service: MagicMock,
    mock_compliance_log_service: MagicMock,
) -> ChatService:
    """
    Return a chat service.
    """

    return ChatService(
        session=mock_async_session,
        conversation_service=mock_conversation_service,
        conversation_event_service=mock_conversation_event_service,
        orchestrator=mock_orchestrator,
        action_workflow_service=mock_action_workflow_service,
        usage_service=mock_usage_service,
        conversation_summarization_service=mock_conversation_summarization_service,
        compliance_log_service=mock_compliance_log_service,
    )


@pytest.fixture
def library_file_service(
    mock_async_session: AsyncMock,
    mock_document_repository: MagicMock,
    mock_storage_client: MagicMock,
) -> LibraryService:
    """
    Return an upload file service.
    """

    return LibraryService(
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
