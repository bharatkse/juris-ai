"""
Repository fixtures.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.agent_action import AgentActionRepository
from src.repositories.approval import ApprovalRepository
from src.repositories.conversation import ConversationRepository
from src.repositories.conversation_event import ConversationEventRepository
from src.repositories.document import DocumentRepository
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
def document_repository(
    db_session: AsyncSession,
) -> DocumentRepository:
    """
    Return a document repository.
    """

    return DocumentRepository(
        session=db_session,
    )


@pytest.fixture
def agent_action_repository(
    db_session: AsyncSession,
) -> AgentActionRepository:
    """
    Return a Agent Action repository.
    """

    return AgentActionRepository(
        session=db_session,
    )


@pytest.fixture
def approval_repository(
    db_session: AsyncSession,
) -> ApprovalRepository:
    """
    Return a approval repository.
    """

    return ApprovalRepository(
        session=db_session,
    )


@pytest.fixture
def mock_document_repository() -> MagicMock:
    """
    Return a mocked document repository.
    """

    return MagicMock(
        spec=DocumentRepository,
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
