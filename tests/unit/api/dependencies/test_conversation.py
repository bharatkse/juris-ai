"""
Unit tests for conversation dependencies.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.api.dependencies.conversation import get_conversation_service


@patch("src.api.dependencies.conversation.ConversationService")
@patch("src.api.dependencies.conversation.UserRepository")
@patch("src.api.dependencies.conversation.ConversationRepository")
def test_get_conversation_service(
    mock_conversation_repository: MagicMock,
    mock_user_repository: MagicMock,
    mock_conversation_service: MagicMock,
) -> None:
    """
    It should create a conversation service.
    """

    session = MagicMock()

    repository = MagicMock()
    user_repository = MagicMock()
    service = MagicMock()

    mock_conversation_repository.return_value = repository
    mock_user_repository.return_value = user_repository
    mock_conversation_service.return_value = service

    result = get_conversation_service(
        session=session,
    )

    assert result is service

    mock_conversation_repository.assert_called_once_with(
        session,
    )

    mock_user_repository.assert_called_once_with(
        session,
    )

    mock_conversation_service.assert_called_once_with(
        session=session,
        repository=repository,
        user_repository=user_repository,
    )
