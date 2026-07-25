"""
Builders for chat service tests.
"""

from __future__ import annotations

from src.services.results.chat import ChatResult
from src.services.results.stream import ChatStreamChunk


def build_chat_stream_chunk(
    **kwargs,
) -> ChatStreamChunk:
    """
    Build a ChatStreamChunk.
    """

    data = {
        "content": "Hello",
        "is_final": False,
        "metadata": {},
    }

    data.update(kwargs)

    return ChatStreamChunk(
        **data,
    )


def build_chat_result(
    **kwargs,
) -> ChatResult:
    """
    Build a ChatResult.
    """

    from tests.factories.conversation import ConversationFactory
    from tests.factories.conversation_event import ConversationEventFactory

    data = {
        "conversation": ConversationFactory.build(),
        "user_event": ConversationEventFactory.build(),
        "assistant_event": ConversationEventFactory.build(),
    }

    data.update(kwargs)

    return ChatResult(
        **data,
    )
