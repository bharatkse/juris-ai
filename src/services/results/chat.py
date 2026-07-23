"""
Chat service result models.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.db.models.conversation import Conversation
from src.db.models.conversation_event import ConversationEvent


@dataclass(slots=True, frozen=True)
class ChatResult:
    """
    Result returned by ChatService.
    """

    conversation: Conversation

    user_event: ConversationEvent

    assistant_event: ConversationEvent
