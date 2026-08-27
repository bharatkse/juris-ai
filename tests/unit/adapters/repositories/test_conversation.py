"""
Unit tests for ConversationRepository.
"""

from __future__ import annotations

import pytest

from core.constants import DEFAULT_CONVERSATION_TITLE
from tests.factories.conversation import ConversationFactory
from tests.factories.user import UserFactory
from tests.helpers.identifiers import unknown_conversation_id


@pytest.mark.asyncio
async def test_create_persists_conversation(
    conversation_repository,
) -> None:
    """
    It should persist a conversation.
    """

    conversation = ConversationFactory.build()

    created = await conversation_repository.create(
        conversation,
    )

    assert created.id == conversation.id
    assert created.title == DEFAULT_CONVERSATION_TITLE


@pytest.mark.asyncio
async def test_create_sets_timestamps(
    conversation_repository,
) -> None:
    """
    It should populate timestamps.
    """

    conversation = ConversationFactory.build()

    created = await conversation_repository.create(
        conversation,
    )

    assert created.created_at is not None
    assert created.updated_at is not None


@pytest.mark.asyncio
async def test_get_returns_existing_conversation(
    conversation_repository,
) -> None:
    """
    It should retrieve an existing conversation.
    """

    conversation = await conversation_repository.create(
        ConversationFactory.build(),
    )

    found = await conversation_repository.get(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
    )

    assert found is not None
    assert found.id == conversation.id
    assert found.title == conversation.title


@pytest.mark.asyncio
async def test_get_returns_none_when_conversation_does_not_exist(
    conversation_repository,
) -> None:
    """
    It should return None for an unknown conversation.
    """

    conversation = ConversationFactory.build()

    found = await conversation_repository.get(
        conversation_id=unknown_conversation_id(),
        user_id=conversation.user_id,
    )

    assert found is None


@pytest.mark.asyncio
async def test_get_returns_none_for_archived_conversation(
    conversation_repository,
) -> None:
    """
    Archived conversations should not be returned.
    """

    conversation = await conversation_repository.create(
        ConversationFactory.build(),
    )

    conversation.archive()

    await conversation_repository.update(
        conversation,
    )

    found = await conversation_repository.get(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
    )

    assert found is None


@pytest.mark.asyncio
async def test_exists_returns_true(
    conversation_repository,
) -> None:
    """
    It should return True when the conversation exists.
    """

    conversation = await conversation_repository.create(
        ConversationFactory.build(),
    )

    exists = await conversation_repository.exists(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
    )

    assert exists is True


@pytest.mark.asyncio
async def test_exists_returns_false(
    conversation_repository,
) -> None:
    """
    It should return False for an unknown conversation.
    """

    conversation = ConversationFactory.build()

    exists = await conversation_repository.exists(
        conversation_id="conv_unknown",
        user_id=conversation.user_id,
    )

    assert exists is False


@pytest.mark.asyncio
async def test_exists_returns_false_for_archived_conversation(
    conversation_repository,
) -> None:
    """
    Archived conversations should not exist.
    """

    conversation = await conversation_repository.create(
        ConversationFactory.build(),
    )

    conversation.archive()

    await conversation_repository.update(
        conversation,
    )

    exists = await conversation_repository.exists(
        conversation_id=conversation.id,
        user_id=conversation.user_id,
    )

    assert exists is False


@pytest.mark.asyncio
async def test_list_returns_empty_list_when_no_conversations_exist(
    conversation_repository,
) -> None:
    """
    It should return an empty list.
    """

    conversation = ConversationFactory.build()

    conversations = await conversation_repository.list(
        user_id=conversation.user_id,
    )

    assert conversations == (
        [],
        0,
    )


@pytest.mark.asyncio
async def test_list_returns_conversations(
    conversation_repository,
) -> None:
    """
    It should return all active conversations.
    """

    user = UserFactory.build()

    first = await conversation_repository.create(
        ConversationFactory.build(
            user=user,
        ),
    )

    second = await conversation_repository.create(
        ConversationFactory.build(
            user=user,
        ),
    )

    conversations, _ = await conversation_repository.list(
        user_id=user.id,
    )

    assert len(conversations) == 2

    assert {conversation.id for conversation in conversations} == {
        first.id,
        second.id,
    }


@pytest.mark.asyncio
async def test_list_excludes_archived_conversations(
    conversation_repository,
) -> None:
    """
    Archived conversations should not be listed.
    """

    active = await conversation_repository.create(
        ConversationFactory.build(),
    )

    archived = await conversation_repository.create(
        ConversationFactory.build(
            user_id=active.user_id,
        ),
    )

    archived.archive()

    await conversation_repository.update(
        archived,
    )

    conversations, _ = await conversation_repository.list(
        user_id=active.user_id,
    )

    assert len(conversations) == 1
    assert conversations[0].id == active.id


@pytest.mark.asyncio
async def test_list_respects_limit(
    conversation_repository,
) -> None:
    """
    It should respect the requested limit.
    """

    user = UserFactory.build()

    for _ in range(5):
        await conversation_repository.create(
            ConversationFactory.build(
                user=user,
            ),
        )

    conversations = await conversation_repository.list(
        user_id=user.id,
        limit=2,
    )

    assert len(conversations) == 2


@pytest.mark.asyncio
async def test_update_persists_archived_conversation(
    conversation_repository,
) -> None:
    """
    It should persist archived conversation updates.
    """

    conversation = await conversation_repository.create(
        ConversationFactory.build(),
    )

    conversation.archive()

    updated = await conversation_repository.update(
        conversation,
    )

    assert updated.deleted_at is not None
