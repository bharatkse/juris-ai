"""
Chat service result models.
"""

from __future__ import annotations

from dataclasses import dataclass

from adapters.persistence.sqlalchemy.models.conversation import Conversation
from adapters.persistence.sqlalchemy.models.conversation_event import ConversationEvent
from agentic.orchestration.schemas.response import OrchestratorResponse
from core.dto.approval import ApprovalRequestDTO


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

    assistant_event: ConversationEvent | None = None

    response: OrchestratorResponse | None = None

    approval: ApprovalRequestDTO | None = None
