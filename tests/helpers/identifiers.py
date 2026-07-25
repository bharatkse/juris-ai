"""
Reusable identifier helpers for tests.
"""

from __future__ import annotations

from src.core.types import ConversationEventId, ConversationId, UserId
from src.db.mixins import generate_prefixed_uuid_pk


def unknown_user_id() -> UserId:
    """
    Return a non-existent user identifier.
    """

    return UserId(
        generate_prefixed_uuid_pk("user"),
    )


def unknown_conversation_id() -> ConversationId:
    """
    Return a non-existent conversation identifier.
    """

    return ConversationId(
        generate_prefixed_uuid_pk("conv"),
    )


def unknown_conversation_event_id() -> ConversationEventId:
    """
    Return a non-existent conversation event identifier.
    """

    return ConversationEventId(
        generate_prefixed_uuid_pk("event"),
    )
