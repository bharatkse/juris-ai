"""
Unit tests for ConversationRepository.
"""

from __future__ import annotations

import pytest

from src.core.constants import DEFAULT_CONVERSATION_TITLE
from tests.factories.conversation import ConversationFactory
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
        conversation.id,
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

    found = await conversation_repository.get(
        unknown_conversation_id(),
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

    await conversation_repository.archive(
        conversation,
    )

    found = await conversation_repository.get(
        conversation.id,
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
        conversation.id,
    )

    assert exists is True


@pytest.mark.asyncio
async def test_exists_returns_false(
    conversation_repository,
) -> None:
    """
    It should return False for an unknown conversation.
    """

    exists = await conversation_repository.exists(
        "conv_unknown",
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

    await conversation_repository.archive(
        conversation,
    )

    exists = await conversation_repository.exists(
        conversation.id,
    )

    assert exists is False


@pytest.mark.asyncio
async def test_list_returns_empty_list_when_no_conversations_exist(
    conversation_repository,
) -> None:
    """
    It should return an empty list.
    """

    conversations = await conversation_repository.list()

    assert conversations == []


@pytest.mark.asyncio
async def test_list_returns_conversations(
    conversation_repository,
) -> None:
    """
    It should return all active conversations.
    """

    await conversation_repository.create(
        ConversationFactory.build(),
    )

    await conversation_repository.create(
        ConversationFactory.build(),
    )

    conversations = await conversation_repository.list()

    assert len(conversations) == 2


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
        ConversationFactory.build(),
    )

    await conversation_repository.archive(
        archived,
    )

    conversations = await conversation_repository.list()

    assert len(conversations) == 1
    assert conversations[0].id == active.id


@pytest.mark.asyncio
async def test_list_respects_limit(
    conversation_repository,
) -> None:
    """
    It should respect the requested limit.
    """

    for _ in range(5):
        await conversation_repository.create(
            ConversationFactory.build(),
        )

    conversations = await conversation_repository.list(
        limit=2,
    )

    assert len(conversations) == 2


@pytest.mark.asyncio
async def test_archive_marks_conversation_as_deleted(
    conversation_repository,
) -> None:
    """
    It should archive the conversation.
    """

    conversation = await conversation_repository.create(
        ConversationFactory.build(),
    )

    await conversation_repository.archive(
        conversation,
    )

    assert conversation.deleted_at is not None
