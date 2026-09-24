"""
Chat service result models.
"""

from __future__ import annotations

from dataclasses import dataclass

from adapters.persistence.sqlalchemy.models.conversation import Conversation
from adapters.persistence.sqlalchemy.models.conversation_event import ConversationEvent
from agentic.orchestration.schemas.response import ApprovalResponse, OrchestratorResponse


@dataclass(
    frozen=True,
    slots=True,
)
class ChatResultDTO:
    """
    Result returned by ChatService.
    """

    conversation: Conversation

    user_event: ConversationEvent

    response: OrchestratorResponse

    assistant_event: ConversationEvent | None = None

    approval: ApprovalResponse | None = None
