"""
Unit tests for ConversationService.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.constants import DEFAULT_CONVERSATION_TITLE
from src.core.exceptions import UserNotFoundError
from src.services.conversation import ConversationService
from tests.builders.schemas import build_create_conversation_request
from tests.factories.conversation import ConversationFactory
from tests.factories.user import UserFactory


@pytest.mark.asyncio
async def test_create_creates_conversation(
    conversation_service: ConversationService,
    mock_conversation_repository: MagicMock,
    mock_user_repository: MagicMock,
) -> None:
    """
    It should create a conversation.
    """

    user = UserFactory.build()
    conversation = ConversationFactory.build(
        user_id=user.id,
    )

    request = build_create_conversation_request(
        user_id=user.id,
        title=conversation.title,
    )

    mock_user_repository.get.return_value = user

    mock_conversation_repository.create.return_value = conversation

    conversation_service.commit = AsyncMock()
    conversation_service.rollback = AsyncMock()

    created = await conversation_service.create(
        request,
    )
    assert created is conversation

    mock_conversation_repository.create.assert_awaited_once()

    mock_user_repository.get.assert_awaited_once_with(
        user.id,
    )

    created_conversation = mock_conversation_repository.create.await_args.args[0]

    assert created_conversation.title == request.title
    assert created_conversation.user_id == request.user_id

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
        user_id=user.id,
        title=None,
    )

    conversation = await conversation_service.create(
        request,
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
        user_id=user.id,
        title="Legal Advice",
    )

    conversation = await conversation_service.create(
        request,
    )

    assert conversation.title == "Legal Advice"

    created_conversation = mock_conversation_repository.create.await_args.args[0]

    assert created_conversation.title == "Legal Advice"
    assert created_conversation.user_id == user.id

    conversation_service.commit.assert_awaited_once_with()
    conversation_service.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_raises_when_user_does_not_exist(
    conversation_service: ConversationService,
    mock_conversation_repository: MagicMock,
    mock_user_repository: MagicMock,
) -> None:
    """
    It should fail when the user does not exist.
    """

    mock_user_repository.get.return_value = None
    conversation_service.commit = AsyncMock()
    conversation_service.rollback = AsyncMock()

    with pytest.raises(
        UserNotFoundError,
    ):
        await conversation_service.create(
            build_create_conversation_request(),
        )

    mock_conversation_repository.create.assert_not_called()

    conversation_service.commit.assert_not_awaited()
    conversation_service.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_rolls_back_when_repository_fails(
    conversation_service: ConversationService,
    mock_conversation_repository: MagicMock,
    mock_user_repository: MagicMock,
) -> None:
    """
    It should roll back when conversation creation fails.
    """

    user = UserFactory.build()

    mock_user_repository.get.return_value = user

    mock_conversation_repository.create.side_effect = RuntimeError(
        "Database error",
    )

    conversation_service.commit = AsyncMock()
    conversation_service.rollback = AsyncMock()

    with pytest.raises(
        RuntimeError,
    ):
        await conversation_service.create(
            build_create_conversation_request(
                user_id=user.id,
            ),
        )

    conversation_service.rollback.assert_awaited_once_with()
    conversation_service.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_rolls_back_when_commit_fails(
    conversation_service: ConversationService,
    mock_conversation_repository: MagicMock,
    mock_user_repository: MagicMock,
) -> None:
    """
    It should roll back when committing fails.
    """

    user = UserFactory.build()

    mock_user_repository.get.return_value = user

    mock_conversation_repository.create.side_effect = lambda conversation: conversation

    conversation_service.commit = AsyncMock(
        side_effect=RuntimeError(
            "Commit failed",
        ),
    )

    conversation_service.rollback = AsyncMock()

    with pytest.raises(
        RuntimeError,
    ):
        await conversation_service.create(
            build_create_conversation_request(
                user_id=user.id,
            ),
        )

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
        conversation.id,
    )

    assert found is conversation

    mock_conversation_repository.get.assert_awaited_once_with(
        conversation.id,
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

    mock_conversation_repository.archive.return_value = None

    conversation_service.commit = AsyncMock()
    conversation_service.rollback = AsyncMock()

    await conversation_service.archive(
        conversation,
    )

    mock_conversation_repository.archive.assert_awaited_once_with(
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

    mock_conversation_repository.archive.side_effect = RuntimeError(
        "Archive failed",
    )

    conversation_service.commit = AsyncMock()
    conversation_service.rollback = AsyncMock()

    with pytest.raises(
        RuntimeError,
    ):
        await conversation_service.archive(
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
    It should roll back when commit fails during archive.
    """

    conversation = ConversationFactory.build()

    mock_conversation_repository.archive.return_value = None

    conversation_service.commit = AsyncMock(
        side_effect=RuntimeError(
            "Commit failed",
        ),
    )

    conversation_service.rollback = AsyncMock()

    with pytest.raises(
        RuntimeError,
    ):
        await conversation_service.archive(
            conversation,
        )

    conversation_service.commit.assert_awaited_once_with()
    conversation_service.rollback.assert_awaited_once_with()
