"""
Frontend context builders.
"""

from __future__ import annotations

from typing import Any

from src.core.config import settings
from src.core.types import UserId
from src.db.models.conversation import Conversation
from src.services.conversation import ConversationService

user_id = "user_123"


async def build_frontend_context(
    *,
    conversation_service: ConversationService,
    user_id: UserId,
    active_conversation_id: str | None = None,
    current_conversation: Conversation | None = None,
    messages: list | None = None,
) -> dict[str, Any]:
    """
    Build the common frontend context.
    """

    conversations = await conversation_service.list(
        user_id=user_id,
    )

    return {
        "conversations": conversations,
        "active_conversation_id": active_conversation_id,
        "current_conversation": current_conversation,
        "messages": messages or [],
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
    }
