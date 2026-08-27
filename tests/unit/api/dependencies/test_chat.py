"""
Unit tests for chat dependencies.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from adapters.persistence.sqlalchemy.repositories.conversation import (
    ConversationRepository,
)
from adapters.persistence.sqlalchemy.repositories.conversation_event import (
    ConversationEventRepository,
)
from api.dependencies.chat import (
    get_chat_service,
    get_conversation_event_repository,
    get_conversation_repository,
)


def test_get_conversation_repository() -> None:
    """
    It should create a conversation repository.
    """

    session = MagicMock()

    repository = get_conversation_repository(
        session=session,
    )

    assert isinstance(
        repository,
        ConversationRepository,
    )

    assert repository._session is session


def test_get_conversation_event_repository() -> None:
    """
    It should create a conversation event repository.
    """

    session = MagicMock()

    repository = get_conversation_event_repository(
        session=session,
    )

    assert isinstance(
        repository,
        ConversationEventRepository,
    )

    assert repository._session is session


@patch("api.dependencies.chat.ChatService")
def test_get_chat_service(
    mock_chat_service: MagicMock,
) -> None:
    """
    It should create a chat service with all required dependencies.
    """

    session = MagicMock()
    conversation_service = MagicMock()
    conversation_event_service = MagicMock()
    orchestrator = MagicMock()
    action_workflow_service = MagicMock()

    service = MagicMock()

    mock_chat_service.return_value = service

    result = get_chat_service(
        session=session,
        conversation_service=conversation_service,
        conversation_event_service=conversation_event_service,
        orchestrator=orchestrator,
        agent_action_workflow_service=action_workflow_service,
    )

    assert result is service

    mock_chat_service.assert_called_once_with(
        session=session,
        conversation_service=conversation_service,
        conversation_event_service=conversation_event_service,
        orchestrator=orchestrator,
        action_workflow_service=action_workflow_service,
    )
