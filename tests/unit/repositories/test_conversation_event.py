"""
Unit tests for ConversationEventRepository.
"""

from __future__ import annotations

import pytest

from src.core.enums import MessageRole
from tests.factories.conversation import ConversationFactory
from tests.factories.user import UserFactory
from tests.helpers.identifiers import unknown_conversation_event_id


async def _create_conversation(user_repository, conversation_repository):
    user = await user_repository.create(
        UserFactory.build(),
    )

    conversation = await conversation_repository.create(
        ConversationFactory.build(
            user=user,
        ),
    )

    return conversation


@pytest.mark.asyncio
async def test_create_user_event(
    conversation_event_repository, user_repository, conversation_repository
) -> None:
    """
    It should create a user event.
    """

    conversation = await _create_conversation(user_repository, conversation_repository)

    event = await conversation_event_repository.create(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content="Hello",
    )

    assert event.id is not None
    assert event.role == MessageRole.USER
    assert event.content == "Hello"


@pytest.mark.asyncio
async def test_create_assistant_event(
    conversation_event_repository, user_repository, conversation_repository
):
    """
    It should create an assistant event.
    """
    conversation = await _create_conversation(user_repository, conversation_repository)

    event = await conversation_event_repository.create(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content="Hi!",
    )

    assert event.role == MessageRole.ASSISTANT


@pytest.mark.asyncio
async def test_create_sets_parent_event(
    conversation_event_repository, user_repository, conversation_repository
):
    """
    It should create a child event.
    """

    conversation = await _create_conversation(user_repository, conversation_repository)

    parent = await conversation_event_repository.create(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content="Question",
    )

    child = await conversation_event_repository.create(
        conversation_id=conversation.id,
        parent_event_id=parent.id,
        role=MessageRole.ASSISTANT,
        content="Answer",
    )

    assert child.parent_event_id == parent.id


@pytest.mark.asyncio
async def test_create_persists_metadata(
    conversation_event_repository, user_repository, conversation_repository
):
    """
    It should persist metadata.
    """

    conversation = await _create_conversation(user_repository, conversation_repository)

    metadata = {
        "provider": "groq",
        "model": "llama",
    }

    event = await conversation_event_repository.create(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content="Hello",
        metadata=metadata,
    )

    assert event.event_metadata == metadata


@pytest.mark.asyncio
async def test_get_returns_existing_event(
    conversation_event_repository, user_repository, conversation_repository
):
    """
    It should retrieve an existing event.
    """

    conversation = await _create_conversation(user_repository, conversation_repository)

    event = await conversation_event_repository.create(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content="Hello",
    )

    found = await conversation_event_repository.get(
        event.id,
    )

    assert found is not None
    assert found.id == event.id


@pytest.mark.asyncio
async def test_get_returns_none_for_unknown_event(
    conversation_event_repository, user_repository, conversation_repository
):
    """
    It should return None for an unknown event.
    """
    await _create_conversation(user_repository, conversation_repository)
    found = await conversation_event_repository.get(unknown_conversation_event_id())

    assert found is None


@pytest.mark.asyncio
async def test_list_by_conversation_returns_all_events(
    conversation_event_repository, user_repository, conversation_repository
):
    """
    It should return all events.
    """

    conversation = await _create_conversation(user_repository, conversation_repository)

    await conversation_event_repository.create(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content="One",
    )

    await conversation_event_repository.create(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content="Two",
    )

    events = await conversation_event_repository.list_by_conversation(
        conversation.id,
    )

    assert len(events) == 2


@pytest.mark.asyncio
async def test_list_by_conversation_orders_by_created_at(
    conversation_event_repository, user_repository, conversation_repository
):
    """
    It should return events chronologically.
    """

    conversation = await _create_conversation(user_repository, conversation_repository)

    first = await conversation_event_repository.create(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content="One",
    )

    second = await conversation_event_repository.create(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content="Two",
    )

    events = await conversation_event_repository.list_by_conversation(
        conversation.id,
    )

    assert events[0].id == first.id
    assert events[1].id == second.id


@pytest.mark.asyncio
async def test_get_recent_events_respects_limit(
    conversation_event_repository, user_repository, conversation_repository
):
    """
    It should respect the requested limit.
    """

    conversation = await _create_conversation(user_repository, conversation_repository)

    for index in range(5):
        await conversation_event_repository.create(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=f"Message {index}",
        )

    events = await conversation_event_repository.get_recent_events(
        conversation_id=conversation.id,
        limit=2,
    )

    assert len(events) == 2


@pytest.mark.asyncio
async def test_get_recent_events_returns_chronological_order(
    conversation_event_repository, user_repository, conversation_repository
):
    """
    Recent events should be returned oldest-to-newest.
    """

    conversation = await _create_conversation(user_repository, conversation_repository)

    for index in range(5):
        await conversation_event_repository.create(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=f"Message {index}",
        )

    events = await conversation_event_repository.get_recent_events(
        conversation_id=conversation.id,
        limit=3,
    )

    assert events[0].content == "Message 2"
    assert events[1].content == "Message 3"
    assert events[2].content == "Message 4"
