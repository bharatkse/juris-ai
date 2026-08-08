"""
Builders for chat service models.
"""

from __future__ import annotations

from typing import Any

from src.services.models.chat import ChatResult
from src.services.models.stream import ChatStreamChunk
from tests.builders.schemas import build_ai_response
from tests.factories.conversation import ConversationFactory
from tests.factories.conversation_event import ConversationEventFactory


def build_chat_result(
    **kwargs: Any,
) -> ChatResult:
    """
    Build a ChatResult.
    """

    conversation = ConversationFactory.build()

    data: dict[str, Any] = {
        "conversation": conversation,
        "user_event": ConversationEventFactory.build(
            conversation_id=conversation.id,
        ),
        "assistant_event": ConversationEventFactory.build(
            conversation_id=conversation.id,
        ),
        "response": build_ai_response(),
    }

    data.update(kwargs)

    return ChatResult(
        **data,
    )


def build_chat_stream_chunk(
    **kwargs: Any,
) -> ChatStreamChunk:
    """
    Build a ChatStreamChunk.
    """

    data: dict[str, Any] = {
        "content": "Hello",
        "is_final": False,
        "response": None,
        "metadata": {},
    }

    data.update(kwargs)

    return ChatStreamChunk(
        **data,
    )
