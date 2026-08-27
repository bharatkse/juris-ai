"""
Unit tests for the ConversationEvent ORM model.
"""

from __future__ import annotations

from core.enums import MessageRoleEnum
from tests.factories.conversation import ConversationFactory
from tests.factories.conversation_event import ConversationEventFactory


def test_role_defaults_to_user() -> None:
    """
    It should default to a user event.
    """

    event = ConversationEventFactory()

    assert event.role == MessageRoleEnum.USER


def test_event_metadata_defaults_to_empty_dict() -> None:
    """
    It should initialize metadata.
    """

    event = ConversationEventFactory()

    assert event.event_metadata == {}


def test_event_has_conversation() -> None:
    """
    It should belong to a conversation.
    """

    event = ConversationEventFactory()

    assert event.conversation is not None


def test_user_message_trait() -> None:
    """
    It should create a user message.
    """

    event = ConversationEventFactory(
        user_message=True,
    )

    assert event.role == MessageRoleEnum.USER


def test_assistant_message_trait() -> None:
    """
    It should create an assistant message.
    """

    event = ConversationEventFactory(
        assistant_message=True,
    )

    assert event.role == MessageRoleEnum.ASSISTANT


def test_system_message_trait() -> None:
    """
    It should create a system message.
    """

    event = ConversationEventFactory(
        system_message=True,
    )

    assert event.role == MessageRoleEnum.SYSTEM


def test_child_event_references_parent() -> None:
    """
    Child events should reference their parent.
    """

    conversation = ConversationFactory()

    parent = ConversationEventFactory(
        conversation=conversation,
        user_message=True,
    )

    child = ConversationEventFactory(
        conversation=conversation,
        assistant_message=True,
        parent_event=parent,
    )

    assert child.parent_event is parent


def test_parent_contains_child_event() -> None:
    """
    Parent events should contain child events.
    """

    conversation = ConversationFactory()

    parent = ConversationEventFactory(
        conversation=conversation,
    )

    child = ConversationEventFactory(
        conversation=conversation,
        parent_event=parent,
    )

    assert child in parent.child_events


def test_parent_and_child_share_conversation() -> None:
    """
    Parent and child should belong to the same conversation.
    """

    conversation = ConversationFactory()

    parent = ConversationEventFactory(
        conversation=conversation,
    )

    child = ConversationEventFactory(
        conversation=conversation,
        parent_event=parent,
    )

    assert parent.conversation == child.conversation


def test_repr_contains_identifier() -> None:
    """
    It should include the identifier.
    """

    event = ConversationEventFactory()

    assert event.id in repr(event)


def test_repr_contains_role() -> None:
    """
    It should include the role.
    """

    event = ConversationEventFactory()

    assert event.role.value in repr(event)
