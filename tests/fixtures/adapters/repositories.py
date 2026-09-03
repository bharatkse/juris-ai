"""
Repository fixtures.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.repositories.agent_action import (
    AgentActionRepository,
)
from adapters.persistence.sqlalchemy.repositories.approval import ApprovalRepository
from adapters.persistence.sqlalchemy.repositories.conversation import (
    ConversationRepository,
)
from adapters.persistence.sqlalchemy.repositories.conversation_event import (
    ConversationEventRepository,
)
from adapters.persistence.sqlalchemy.repositories.library_file import LibraryFileRepository
from adapters.persistence.sqlalchemy.repositories.user import UserRepository


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
def upload_file_repository(
    db_session: AsyncSession,
) -> LibraryFileRepository:
    """
    Return a upload file repository.
    """

    return LibraryFileRepository(
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
def mock_upload_file_repository() -> MagicMock:
    """
    Return a mocked upload file repository.
    """

    return MagicMock(
        spec=LibraryFileRepository,
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

    repository = MagicMock(
        spec=UserRepository,
    )

    repository.get_by_email = AsyncMock()
    repository.get = AsyncMock()

    return repository
