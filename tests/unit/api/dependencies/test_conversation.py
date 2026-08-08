"""
Unit tests for conversation dependencies.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.api.dependencies.conversation import get_conversation_service


@patch("src.api.dependencies.conversation.ConversationService")
def test_get_conversation_service(
    mock_conversation_service: MagicMock,
) -> None:
    """
    It should create a conversation service.
    """

    session = MagicMock()
    repository = MagicMock()
    service = MagicMock()

    mock_conversation_service.return_value = service

    result = get_conversation_service(
        session=session,
        repository=repository,
    )

    assert result is service

    mock_conversation_service.assert_called_once_with(
        session=session,
        repository=repository,
    )
