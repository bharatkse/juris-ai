"""
Unit tests for ConversationEventRepository.
"""

from __future__ import annotations

import pytest

from src.core.enums import MessageRole
from src.db.models.conversation_event import ConversationEvent
from tests.factories.conversation import ConversationFactory
from tests.factories.user import UserFactory
from tests.helpers.identifiers import unknown_conversation_event_id


async def _create_conversation(
    user_repository,
    conversation_repository,
):
    user = await user_repository.create(
        UserFactory.build(),
    )

    return await conversation_repository.create(
        ConversationFactory.build(
            user=user,
        ),
    )


@pytest.mark.asyncio
async def test_create_user_event(
    conversation_event_repository,
    user_repository,
    conversation_repository,
) -> None:
    """
    It should create a user event.
    """

    conversation = await _create_conversation(
        user_repository,
        conversation_repository,
    )

    event = ConversationEvent(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content="Hello",
        event_metadata={},
    )

    created = await conversation_event_repository.create(
        event,
    )

    assert created.id is not None
    assert created.role == MessageRole.USER
    assert created.content == "Hello"


@pytest.mark.asyncio
async def test_create_assistant_event(
    conversation_event_repository,
    user_repository,
    conversation_repository,
) -> None:
    """
    It should create an assistant event.
    """

    conversation = await _create_conversation(
        user_repository,
        conversation_repository,
    )

    event = ConversationEvent(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content="Hi!",
        event_metadata={},
    )

    created = await conversation_event_repository.create(
        event,
    )

    assert created.role == MessageRole.ASSISTANT


@pytest.mark.asyncio
async def test_create_sets_parent_event(
    conversation_event_repository,
    user_repository,
    conversation_repository,
) -> None:
    """
    It should create a child event.
    """

    conversation = await _create_conversation(
        user_repository,
        conversation_repository,
    )

    parent = await conversation_event_repository.create(
        ConversationEvent(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="Question",
            event_metadata={},
        ),
    )

    child = await conversation_event_repository.create(
        ConversationEvent(
            conversation_id=conversation.id,
            parent_event_id=parent.id,
            role=MessageRole.ASSISTANT,
            content="Answer",
            event_metadata={},
        ),
    )

    assert child.parent_event_id == parent.id


@pytest.mark.asyncio
async def test_create_persists_metadata(
    conversation_event_repository,
    user_repository,
    conversation_repository,
) -> None:
    """
    It should persist metadata.
    """

    conversation = await _create_conversation(
        user_repository,
        conversation_repository,
    )

    metadata = {
        "provider": "groq",
        "model": "llama",
    }

    event = await conversation_event_repository.create(
        ConversationEvent(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="Hello",
            event_metadata=metadata,
        ),
    )

    assert event.event_metadata == metadata


@pytest.mark.asyncio
async def test_get_returns_existing_event(
    conversation_event_repository,
    user_repository,
    conversation_repository,
) -> None:
    """
    It should retrieve an existing event.
    """

    conversation = await _create_conversation(
        user_repository,
        conversation_repository,
    )

    event = await conversation_event_repository.create(
        ConversationEvent(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="Hello",
            event_metadata={},
        ),
    )

    found = await conversation_event_repository.get(
        conversation_id=conversation.id,
        event_id=event.id,
    )

    assert found is not None
    assert found.id == event.id


@pytest.mark.asyncio
async def test_get_returns_none_for_unknown_event(
    conversation_event_repository,
    user_repository,
    conversation_repository,
) -> None:
    """
    It should return None for an unknown event.
    """

    conversation = await _create_conversation(
        user_repository,
        conversation_repository,
    )

    found = await conversation_event_repository.get(
        conversation_id=conversation.id,
        event_id=unknown_conversation_event_id(),
    )

    assert found is None


@pytest.mark.asyncio
async def test_list_returns_all_events(
    conversation_event_repository,
    user_repository,
    conversation_repository,
) -> None:
    """
    It should return all events.
    """

    conversation = await _create_conversation(
        user_repository,
        conversation_repository,
    )

    await conversation_event_repository.create(
        ConversationEvent(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="One",
            event_metadata={},
        ),
    )

    await conversation_event_repository.create(
        ConversationEvent(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content="Two",
            event_metadata={},
        ),
    )

    events = await conversation_event_repository.list(
        conversation_id=conversation.id,
    )

    assert len(events) == 2


@pytest.mark.asyncio
async def test_list_orders_by_created_at(
    conversation_event_repository,
    user_repository,
    conversation_repository,
) -> None:
    """
    It should return events chronologically.
    """

    conversation = await _create_conversation(
        user_repository,
        conversation_repository,
    )

    first = await conversation_event_repository.create(
        ConversationEvent(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="One",
            event_metadata={},
        ),
    )

    second = await conversation_event_repository.create(
        ConversationEvent(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content="Two",
            event_metadata={},
        ),
    )

    events = await conversation_event_repository.list(
        conversation_id=conversation.id,
    )

    assert events[0].id == first.id
    assert events[1].id == second.id


@pytest.mark.asyncio
async def test_list_respects_limit(
    conversation_event_repository,
    user_repository,
    conversation_repository,
) -> None:
    """
    It should respect the requested limit.
    """

    conversation = await _create_conversation(
        user_repository,
        conversation_repository,
    )

    for index in range(5):
        await conversation_event_repository.create(
            ConversationEvent(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=f"Message {index}",
                event_metadata={},
            ),
        )

    events = await conversation_event_repository.list(
        conversation_id=conversation.id,
        limit=2,
    )

    assert len(events) == 2


@pytest.mark.asyncio
async def test_list_returns_recent_events_in_chronological_order(
    conversation_event_repository,
    user_repository,
    conversation_repository,
) -> None:
    """
    Limited results should still be returned oldest-to-newest.
    """

    conversation = await _create_conversation(
        user_repository,
        conversation_repository,
    )

    for index in range(5):
        await conversation_event_repository.create(
            ConversationEvent(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=f"Message {index}",
                event_metadata={},
            ),
        )

    events = await conversation_event_repository.list(
        conversation_id=conversation.id,
        limit=3,
    )

    assert len(events) == 3
    assert events[0].content == "Message 2"
    assert events[1].content == "Message 3"
    assert events[2].content == "Message 4"
