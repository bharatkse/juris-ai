"""
Unit tests for ConversationService.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from src.core.constants import DEFAULT_CONVERSATION_TITLE
from src.core.exceptions.database import DatabaseError
from src.services.conversation import ConversationService
from tests.builders.schemas import build_create_conversation_request
from tests.factories.conversation import ConversationFactory
from tests.factories.user import UserFactory


@pytest.mark.asyncio
async def test_create_creates_conversation(
    conversation_service: ConversationService,
    mock_conversation_repository: MagicMock,
) -> None:
    """
    It should create a conversation.
    """

    user = UserFactory.build()

    conversation = ConversationFactory.build(
        user_id=user.id,
        title="Legal",
    )

    mock_conversation_repository.create.return_value = conversation

    conversation_service.commit = AsyncMock()
    conversation_service.rollback = AsyncMock()

    request = build_create_conversation_request(
        title="Legal",
    )

    created = await conversation_service.create(
        user_id=user.id,
        request=request,
    )

    assert created is conversation

    mock_conversation_repository.create.assert_awaited_once()

    created_conversation = mock_conversation_repository.create.await_args.args[0]

    assert created_conversation.title == request.title
    assert created_conversation.user_id == user.id

    conversation_service.commit.assert_awaited_once_with()
    conversation_service.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_uses_default_title(
    conversation_service: ConversationService,
    mock_conversation_repository: MagicMock,
    mock_user_repository: MagicMock,
) -> None:
    """
    It should use the default title when one is not provided.
    """

    user = UserFactory.build()

    mock_user_repository.get.return_value = user

    mock_conversation_repository.create.side_effect = lambda conversation: conversation

    conversation_service.commit = AsyncMock()
    conversation_service.rollback = AsyncMock()

    request = build_create_conversation_request(
        title=None,
    )

    conversation = await conversation_service.create(
        request=request,
        user_id=user.id,
    )

    assert conversation.title == DEFAULT_CONVERSATION_TITLE

    created_conversation = mock_conversation_repository.create.await_args.args[0]

    assert created_conversation.title == DEFAULT_CONVERSATION_TITLE
    assert created_conversation.user_id == user.id

    conversation_service.commit.assert_awaited_once_with()
    conversation_service.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_uses_custom_title(
    conversation_service: ConversationService,
    mock_conversation_repository: MagicMock,
    mock_user_repository: MagicMock,
) -> None:
    """
    It should preserve a custom title.
    """

    user = UserFactory.build()

    mock_user_repository.get.return_value = user

    mock_conversation_repository.create.side_effect = lambda conversation: conversation

    conversation_service.commit = AsyncMock()
    conversation_service.rollback = AsyncMock()

    request = build_create_conversation_request(
        title="Legal Advice",
    )

    conversation = await conversation_service.create(
        request=request,
        user_id=user.id,
    )

    assert conversation.title == "Legal Advice"

    created_conversation = mock_conversation_repository.create.await_args.args[0]

    assert created_conversation.title == "Legal Advice"
    assert created_conversation.user_id == user.id

    conversation_service.commit.assert_awaited_once_with()
    conversation_service.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_rolls_back_when_repository_fails(
    conversation_service: ConversationService,
    mock_conversation_repository: MagicMock,
) -> None:
    """
    It should roll back when conversation creation fails.
    """

    user = UserFactory.build()

    mock_conversation_repository.create.side_effect = SQLAlchemyError(
        "Database error",
    )

    conversation_service.commit = AsyncMock()
    conversation_service.rollback = AsyncMock()

    request = build_create_conversation_request(
        title="Legal",
    )

    with pytest.raises(DatabaseError):
        await conversation_service.create(
            user_id=user.id,
            request=request,
        )

    mock_conversation_repository.create.assert_awaited_once()

    conversation_service.rollback.assert_awaited_once_with()
    conversation_service.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_rolls_back_when_commit_fails(
    conversation_service: ConversationService,
    mock_conversation_repository: MagicMock,
) -> None:
    """
    It should roll back when committing the conversation fails.
    """

    user = UserFactory.build()

    conversation = ConversationFactory.build(
        user_id=user.id,
    )

    mock_conversation_repository.create.return_value = conversation

    conversation_service.commit = AsyncMock(
        side_effect=SQLAlchemyError(
            "Commit failed",
        ),
    )

    conversation_service.rollback = AsyncMock()

    request = build_create_conversation_request(
        title="Legal",
    )

    with pytest.raises(DatabaseError):
        await conversation_service.create(
            user_id=user.id,
            request=request,
        )

    mock_conversation_repository.create.assert_awaited_once()

    conversation_service.commit.assert_awaited_once_with()
    conversation_service.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_get_returns_conversation(
    conversation_service: ConversationService,
    mock_conversation_repository: MagicMock,
) -> None:
    """
    It should return the requested conversation.
    """

    conversation = ConversationFactory.build()

    mock_conversation_repository.get.return_value = conversation

    found = await conversation_service.get(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
    )

    assert found is conversation

    mock_conversation_repository.get.assert_awaited_once_with(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
    )


@pytest.mark.asyncio
async def test_archive_archives_conversation(
    conversation_service: ConversationService,
    mock_conversation_repository: MagicMock,
) -> None:
    """
    It should archive a conversation.
    """

    conversation = ConversationFactory.build()

    mock_conversation_repository.get.return_value = conversation
    mock_conversation_repository.update.return_value = conversation

    conversation_service.commit = AsyncMock()
    conversation_service.rollback = AsyncMock()

    result = await conversation_service.archive(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
    )

    assert result is conversation
    assert conversation.is_active is False

    mock_conversation_repository.get.assert_awaited_once_with(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
    )

    mock_conversation_repository.update.assert_awaited_once_with(
        conversation,
    )

    conversation_service.commit.assert_awaited_once_with()
    conversation_service.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_archive_rolls_back_when_repository_fails(
    conversation_service: ConversationService,
    mock_conversation_repository: MagicMock,
) -> None:
    """
    It should roll back when archiving fails.
    """

    conversation = ConversationFactory.build()

    mock_conversation_repository.get.return_value = conversation

    mock_conversation_repository.update.side_effect = SQLAlchemyError(
        "Archive failed",
    )

    conversation_service.commit = AsyncMock()
    conversation_service.rollback = AsyncMock()

    with pytest.raises(DatabaseError):
        await conversation_service.archive(
            conversation_id=conversation.id,
            user_id=conversation.user_id,
        )

    mock_conversation_repository.get.assert_awaited_once_with(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
    )

    mock_conversation_repository.update.assert_awaited_once_with(
        conversation,
    )

    conversation_service.rollback.assert_awaited_once_with()
    conversation_service.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_archive_rolls_back_when_commit_fails(
    conversation_service: ConversationService,
    mock_conversation_repository: MagicMock,
) -> None:
    """
    It should roll back when committing the archive fails.
    """

    conversation = ConversationFactory.build()

    mock_conversation_repository.get.return_value = conversation
    mock_conversation_repository.update.return_value = conversation

    conversation_service.commit = AsyncMock(
        side_effect=SQLAlchemyError(
            "Commit failed",
        ),
    )

    conversation_service.rollback = AsyncMock()

    with pytest.raises(DatabaseError):
        await conversation_service.archive(
            conversation_id=conversation.id,
            user_id=conversation.user_id,
        )

    mock_conversation_repository.update.assert_awaited_once_with(
        conversation,
    )

    conversation_service.commit.assert_awaited_once_with()
    conversation_service.rollback.assert_awaited_once_with()
