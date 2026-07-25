"""
Unit tests for ChatResult & ChatStreamChunk.
"""

from __future__ import annotations

from src.services.results.chat import ChatResult
from src.services.results.stream import ChatStreamChunk
from tests.factories.conversation import ConversationFactory
from tests.factories.conversation_event import ConversationEventFactory


def test_chat_result_stores_values() -> None:
    """
    It should store the chat result.
    """

    conversation = ConversationFactory.build()

    user_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
    )

    assistant_event = ConversationEventFactory.build(
        conversation_id=conversation.id,
    )

    result = ChatResult(
        conversation=conversation,
        user_event=user_event,
        assistant_event=assistant_event,
    )

    assert result.conversation is conversation
    assert result.user_event is user_event
    assert result.assistant_event is assistant_event


def test_chat_stream_chunk_stores_values() -> None:
    """
    It should store stream chunk values.
    """

    chunk = ChatStreamChunk(
        content="Hello",
        is_final=True,
        metadata={
            "foo": "bar",
        },
    )

    assert chunk.content == "Hello"
    assert chunk.is_final is True
    assert chunk.metadata == {
        "foo": "bar",
    }
