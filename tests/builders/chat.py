"""
Builders for chat service models.
"""

from __future__ import annotations

from typing import Any

from src.core.enums import MessageRoleEnum
from src.services.dto.chat import ChatResultDTO
from src.services.dto.stream import ChatStreamChunkDTO
from tests.builders.orchestrator import build_orchestrator_response
from tests.factories.conversation import ConversationFactory
from tests.factories.conversation_event import ConversationEventFactory


def build_chat_result(
    *,
    conversation=None,
    response=None,
    user_event=None,
    assistant_event=None,
) -> ChatResultDTO:
    conversation = conversation or ConversationFactory.build()

    response = response or build_orchestrator_response(
        conversation_id=conversation.id,
        content="Hello!",
    )

    user_event = user_event or ConversationEventFactory.build(
        conversation_id=conversation.id,
        role=MessageRoleEnum.USER,
        content="Hello",
    )

    assistant_event = assistant_event or ConversationEventFactory.build(
        conversation_id=conversation.id,
        role=MessageRoleEnum.ASSISTANT,
        content="Hello!",
        parent_event_id=user_event.id,
    )

    return ChatResultDTO(
        conversation=conversation,
        user_event=user_event,
        assistant_event=assistant_event,
        response=response,
    )


def build_chat_stream_chunk(
    **kwargs: Any,
) -> ChatStreamChunkDTO:
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

    return ChatStreamChunkDTO(
        **data,
    )
