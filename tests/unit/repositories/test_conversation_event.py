"""
Unit tests for ConversationEventRepository.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.core.enums import MessageRoleEnum
from tests.factories.conversation_event import ConversationEventFactory
from tests.helpers.identifiers import unknown_conversation_event_id


@pytest.mark.asyncio
async def test_create_user_event(
    conversation_event_repository,
    conversation,
) -> None:
    """
    It should create a user event.
    """

    event = ConversationEventFactory.build(
        conversation=conversation,
        request_id=uuid4(),
        user_message=True,
        content="Hello",
    )

    created = await conversation_event_repository.create(
        event,
    )

    assert created.id is not None
    assert created.conversation_id == conversation.id
    assert created.request_id is not None
    assert created.role == MessageRoleEnum.USER
    assert created.content == "Hello"


@pytest.mark.asyncio
async def test_create_assistant_event(
    conversation_event_repository,
    conversation,
) -> None:
    """
    It should create an assistant event.
    """

    event = ConversationEventFactory.build(
        conversation=conversation,
        request_id=uuid4(),
        assistant_message=True,
        content="Hi!",
    )

    created = await conversation_event_repository.create(
        event,
    )

    assert created.id is not None
    assert created.conversation_id == conversation.id
    assert created.request_id is not None
    assert created.role == MessageRoleEnum.ASSISTANT
    assert created.content == "Hi!"


@pytest.mark.asyncio
async def test_create_sets_parent_event(
    conversation_event_repository,
    conversation,
) -> None:
    """
    It should create a child event.
    """

    request_id = uuid4()

    parent = await conversation_event_repository.create(
        ConversationEventFactory.build(
            conversation=conversation,
            request_id=request_id,
            user_message=True,
            content="Question",
        ),
    )

    child = await conversation_event_repository.create(
        ConversationEventFactory.build(
            conversation=conversation,
            request_id=request_id,
            parent_event=parent,
            assistant_message=True,
            content="Answer",
        ),
    )

    assert child.id is not None
    assert child.parent_event_id == parent.id
    assert child.request_id == request_id
    assert child.role == MessageRoleEnum.ASSISTANT


@pytest.mark.asyncio
async def test_create_persists_metadata(
    conversation_event_repository,
    conversation,
) -> None:
    """
    It should persist metadata.
    """

    metadata = {
        "provider": "groq",
        "model": "llama",
    }

    event = ConversationEventFactory.build(
        conversation=conversation,
        request_id=uuid4(),
        user_message=True,
        content="Hello",
        event_metadata=metadata,
    )

    created = await conversation_event_repository.create(
        event,
    )

    assert created.event_metadata == metadata


@pytest.mark.asyncio
async def test_get_returns_existing_event(
    conversation_event_repository,
    conversation,
) -> None:
    """
    It should retrieve an existing event.
    """

    event = await conversation_event_repository.create(
        ConversationEventFactory.build(
            conversation=conversation,
            request_id=uuid4(),
            user_message=True,
            content="Hello",
        ),
    )

    found = await conversation_event_repository.get(
        conversation_id=conversation.id,
        event_id=event.id,
    )

    assert found is not None
    assert found.id == event.id
    assert found.conversation_id == conversation.id


@pytest.mark.asyncio
async def test_get_returns_none_for_unknown_event(
    conversation_event_repository,
    conversation,
) -> None:
    """
    It should return None for an unknown event.
    """

    found = await conversation_event_repository.get(
        conversation_id=conversation.id,
        event_id=unknown_conversation_event_id(),
    )

    assert found is None


@pytest.mark.asyncio
async def test_list_returns_all_events(
    conversation_event_repository,
    conversation,
) -> None:
    """
    It should return all events.
    """

    request_id = uuid4()

    await conversation_event_repository.create(
        ConversationEventFactory.build(
            conversation=conversation,
            request_id=request_id,
            user_message=True,
            content="One",
        ),
    )

    await conversation_event_repository.create(
        ConversationEventFactory.build(
            conversation=conversation,
            request_id=request_id,
            assistant_message=True,
            content="Two",
        ),
    )

    events = await conversation_event_repository.list(
        conversation_id=conversation.id,
    )

    assert len(events) == 2
    assert events[0].content == "One"
    assert events[1].content == "Two"


@pytest.mark.asyncio
async def test_list_orders_by_created_at(
    conversation_event_repository,
    conversation,
) -> None:
    """
    It should return events chronologically.
    """

    request_id = uuid4()

    first = await conversation_event_repository.create(
        ConversationEventFactory.build(
            conversation=conversation,
            request_id=request_id,
            user_message=True,
            content="One",
        ),
    )

    second = await conversation_event_repository.create(
        ConversationEventFactory.build(
            conversation=conversation,
            request_id=request_id,
            assistant_message=True,
            content="Two",
        ),
    )

    events = await conversation_event_repository.list(
        conversation_id=conversation.id,
    )

    assert len(events) == 2
    assert events[0].id == first.id
    assert events[1].id == second.id


@pytest.mark.asyncio
async def test_list_respects_limit(
    conversation_event_repository,
    conversation,
) -> None:
    """
    It should respect the requested limit.
    """

    for index in range(5):
        await conversation_event_repository.create(
            ConversationEventFactory.build(
                conversation=conversation,
                request_id=uuid4(),
                user_message=True,
                content=f"Message {index}",
            ),
        )

    events = await conversation_event_repository.list(
        conversation_id=conversation.id,
        limit=2,
    )

    assert len(events) == 2
    assert events[0].content == "Message 3"
    assert events[1].content == "Message 4"


@pytest.mark.asyncio
async def test_list_returns_recent_events_in_chronological_order(
    conversation_event_repository,
    conversation,
) -> None:
    """
    Limited results should still be returned oldest-to-newest.
    """

    for index in range(5):
        await conversation_event_repository.create(
            ConversationEventFactory.build(
                conversation=conversation,
                request_id=uuid4(),
                user_message=True,
                content=f"Message {index}",
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
