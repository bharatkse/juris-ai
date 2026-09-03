"""
Reusable identifier helpers for tests.
"""

from __future__ import annotations

from uuid import uuid4

from adapters.persistence.sqlalchemy.mixins import generate_prefixed_uuid_pk
from core.types import (
    AgentActionId,
    ApprovalId,
    ConversationEventId,
    ConversationId,
    LibraryFileId,
    UserId,
)


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
        generate_prefixed_uuid_pk("evnt"),
    )


def unknown_request_id() -> str:
    """
    Return a non-existent request identifier.
    """

    return str(uuid4())


def unknown_agent_action_id() -> AgentActionId:
    """
    Return a non-existent agent action identifier.
    """
    return AgentActionId(
        generate_prefixed_uuid_pk("actn"),
    )


def unknown_approval_id() -> ApprovalId:
    """
    Return a non-existent approval identifier.
    """
    return ApprovalId(
        generate_prefixed_uuid_pk("appr"),
    )


def unknown_upload_file_id() -> LibraryFileId:
    """
    Return a non-existent upload file identifier.
    """
    return LibraryFileId(
        generate_prefixed_uuid_pk("upld"),
    )
