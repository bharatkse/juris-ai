"""
Unit tests for chat dependencies.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.agents.base import BaseAgent
from src.api.dependencies.chat import (
    get_chat_service,
    get_conversation_event_repository,
    get_conversation_repository,
    get_groq_client,
    get_legal_agent,
)
from src.clients.groq import GroqClient
from src.repositories.conversation import ConversationRepository
from src.repositories.conversation_event import ConversationEventRepository


def test_get_groq_client_returns_shared_instance() -> None:
    """
    It should return the shared Groq client.
    """

    client = get_groq_client()

    assert isinstance(
        client,
        GroqClient,
    )

    assert client is get_groq_client()


def test_get_legal_agent_returns_shared_instance() -> None:
    """
    It should return the shared legal agent.
    """

    agent = get_legal_agent()

    assert isinstance(
        agent,
        BaseAgent,
    )

    assert agent is get_legal_agent()


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


@patch("src.api.dependencies.chat.ChatService")
def test_get_chat_service(
    mock_chat_service: MagicMock,
) -> None:
    """
    It should create a chat service.
    """

    session = MagicMock()
    conversation_repository = MagicMock()
    event_repository = MagicMock()
    agent = MagicMock()

    service = MagicMock()

    mock_chat_service.return_value = service

    result = get_chat_service(
        session=session,
        conversation_repository=conversation_repository,
        event_repository=event_repository,
        agent=agent,
    )

    assert result is service

    mock_chat_service.assert_called_once_with(
        session=session,
        conversation_repository=conversation_repository,
        event_repository=event_repository,
        agent=agent,
    )
