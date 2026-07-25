"""
Unit tests for the Conversation ORM model.
"""

from __future__ import annotations

from src.core.constants import DEFAULT_CONVERSATION_TITLE
from tests.factories.conversation import ConversationFactory


def test_title_defaults_to_default_conversation_title() -> None:
    """
    It should use the default conversation title.
    """

    conversation = ConversationFactory()

    assert conversation.title == DEFAULT_CONVERSATION_TITLE


def test_conversation_is_active_by_default() -> None:
    """
    Newly created conversations should be active.
    """

    conversation = ConversationFactory()

    assert conversation.is_active is True


def test_archived_trait_creates_inactive_conversation() -> None:
    """
    The archived trait should create an inactive conversation.
    """

    conversation = ConversationFactory(
        archived=True,
    )

    assert conversation.is_active is False
    assert conversation.deleted_at is not None


def test_archive_marks_conversation_as_inactive() -> None:
    """
    It should archive the conversation.
    """

    conversation = ConversationFactory()

    conversation.archive()

    assert conversation.is_active is False


def test_archive_sets_deleted_at() -> None:
    """
    It should set deleted_at when archived.
    """

    conversation = ConversationFactory()

    conversation.archive()

    assert conversation.deleted_at is not None


def test_repr_contains_identifier() -> None:
    """
    It should include the conversation identifier.
    """

    conversation = ConversationFactory()

    assert conversation.id in repr(conversation)


def test_repr_contains_title() -> None:
    """
    It should include the conversation title.
    """

    conversation = ConversationFactory()

    assert conversation.title in repr(conversation)


def test_archive_is_idempotent() -> None:
    """
    Archiving an already archived conversation should not fail.
    """

    conversation = ConversationFactory()

    conversation.archive()

    deleted_at = conversation.deleted_at

    conversation.archive()

    assert conversation.deleted_at == deleted_at
