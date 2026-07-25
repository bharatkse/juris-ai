"""
Repository fixtures.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.conversation import ConversationRepository
from src.repositories.conversation_event import ConversationEventRepository
from src.repositories.user import UserRepository


@pytest.fixture
def conversation_repository(
    db_session: AsyncSession,
) -> ConversationRepository:
    """
    Return a conversation repository.
    """

    return ConversationRepository(
        session=db_session,
    )


@pytest.fixture
def conversation_event_repository(
    db_session: AsyncSession,
) -> ConversationEventRepository:
    """
    Return a conversation event repository.
    """

    return ConversationEventRepository(
        session=db_session,
    )


@pytest.fixture
def user_repository(
    db_session: AsyncSession,
) -> UserRepository:
    """
    Return a user repository.
    """

    return UserRepository(
        session=db_session,
    )


@pytest.fixture
def mock_conversation_repository() -> MagicMock:
    """
    Return a mocked conversation repository.
    """

    return MagicMock(
        spec=ConversationRepository,
    )


@pytest.fixture
def mock_conversation_event_repository() -> MagicMock:
    """
    Return a mocked conversation event repository.
    """

    return MagicMock(
        spec=ConversationEventRepository,
    )


@pytest.fixture
def mock_user_repository() -> MagicMock:
    """
    Return a mocked user repository.
    """

    return MagicMock(
        spec=UserRepository,
    )
