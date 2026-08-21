"""
Chat service result models.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.dto.approval import ApprovalRequestDTO
from src.db.models.conversation import Conversation
from src.db.models.conversation_event import ConversationEvent
from src.orchestration.schemas.response import AgentResponse


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

    response: AgentResponse | None = None

    approval: ApprovalRequestDTO | None = None
