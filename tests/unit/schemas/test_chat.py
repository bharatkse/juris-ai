"""
Unit tests for chat schemas.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from agentic.orchestration.schemas.response import ResponseMetadata, Usage
from api.schemas.chat import (
    AIResponse,
    ChatRequest,
    ChatResponse,
    ChatStreamResponse,
    ConversationEventResponse,
)
from core.enums import MessageRoleEnum
from tests.builders.api.schemas import build_chat_request
from tests.factories.conversation_event import ConversationEventFactory
from tests.helpers.identifiers import unknown_conversation_id


def test_chat_request_accepts_valid_request() -> None:
    """
    It should accept a valid request.
    """

    request = build_chat_request()

    assert request.conversation_id.startswith("conv_")
    assert request.message == "Hello"


def test_chat_request_requires_conversation_id() -> None:
    """
    It should require a conversation identifier.
    """

    with pytest.raises(ValidationError):
        ChatRequest(
            message="Hello",
        )


def test_chat_request_requires_message() -> None:
    """
    It should require a message.
    """

    with pytest.raises(ValidationError):
        ChatRequest(
            conversation_id="conv_123",
        )


def test_chat_request_rejects_empty_message() -> None:
    """
    It should reject an empty message.
    """

    with pytest.raises(ValidationError):
        build_chat_request(
            message="",
        )


def test_chat_request_rejects_message_longer_than_limit() -> None:
    """
    It should reject messages longer than the maximum length.
    """

    with pytest.raises(ValidationError):
        build_chat_request(
            message="a" * 10_001,
        )


def test_chat_request_rejects_extra_fields() -> None:
    """
    It should reject unexpected fields.
    """

    with pytest.raises(ValidationError):
        ChatRequest(
            conversation_id="conv_123",
            message="Hello",
            unknown="value",
        )


def test_conversation_event_response_can_be_created_from_entity() -> None:
    """
    It should create a response from a conversation event.
    """

    event = ConversationEventFactory.build()

    response = ConversationEventResponse.model_validate(
        event,
    )

    assert response.id == event.id
    assert response.conversation_id == event.conversation_id
    assert response.parent_event_id == event.parent_event_id
    assert response.role == event.role
    assert response.content == event.content
    assert response.metadata == event.event_metadata
    assert response.created_at == event.created_at


def test_conversation_event_response_serializes_metadata_alias() -> None:
    """
    It should serialize metadata using the event_metadata alias.
    """

    event = ConversationEventFactory.build()

    response = ConversationEventResponse.model_validate(
        event,
    )

    data = response.model_dump(
        by_alias=True,
    )

    assert "event_metadata" in data
    assert "metadata" not in data
    assert data["event_metadata"] == event.event_metadata


def test_conversation_event_response_rejects_extra_fields() -> None:
    """
    It should reject unexpected fields.
    """

    with pytest.raises(ValidationError):
        ConversationEventResponse(
            id="event_123",
            conversation_id="conv_123",
            parent_event_id=None,
            role=MessageRoleEnum.USER,
            content="Hello",
            event_metadata={},
            created_at=datetime.now(),
            unknown="value",
        )


def test_ai_response_accepts_valid_response() -> None:
    """
    It should accept a valid AI response.
    """

    response = AIResponse(
        content="Legal answer",
        usage=Usage(
            provider="groq",
            model="llama-3.3-70b-versatile",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_ms=120.5,
        ),
        metadata=ResponseMetadata(
            agents=["legal"],
            workflow="legal_qa",
        ),
    )

    assert response.content == "Legal answer"

    assert response.usage.provider == "groq"
    assert response.usage.model == "llama-3.3-70b-versatile"
    assert response.usage.prompt_tokens == 100
    assert response.usage.completion_tokens == 50
    assert response.usage.total_tokens == 150
    assert response.usage.latency_ms == 120.5

    assert response.metadata.agents == ["legal"]
    assert response.metadata.workflow == "legal_qa"


def test_ai_response_uses_defaults() -> None:
    """
    It should use defaults for optional response fields.
    """

    response = AIResponse(
        content="Legal answer",
    )

    assert response.content == "Legal answer"
    assert response.citations == []
    assert response.sources == []
    assert response.usage.provider is None
    assert response.usage.model is None
    assert response.usage.prompt_tokens == 0
    assert response.usage.completion_tokens == 0
    assert response.usage.total_tokens == 0
    assert response.usage.latency_ms is None
    assert response.metadata.agents == []
    assert response.metadata.workflow is None


def test_ai_response_rejects_extra_fields() -> None:
    """
    It should reject unexpected fields.
    """

    with pytest.raises(ValidationError):
        AIResponse(
            content="Legal answer",
            message="Unexpected field",
        )


def test_ai_response_rejects_invalid_metadata() -> None:
    """
    It should reject metadata fields that are not part of
    ResponseMetadata.
    """

    with pytest.raises(ValidationError):
        AIResponse(
            content="Legal answer",
            metadata={
                "provider": "groq",
            },
        )


def test_chat_response_accepts_valid_response() -> None:
    """
    It should accept a valid chat response.
    """

    user_event = ConversationEventResponse.model_validate(
        ConversationEventFactory.build(
            role=MessageRoleEnum.USER,
        ),
    )

    assistant_event = ConversationEventResponse.model_validate(
        ConversationEventFactory.build(
            role=MessageRoleEnum.ASSISTANT,
        ),
    )

    ai_response = AIResponse(
        content="Legal answer",
        usage=Usage(
            provider="groq",
            model="llama-3.3-70b-versatile",
        ),
        metadata=ResponseMetadata(
            agents=["legal"],
            workflow="legal_qa",
        ),
    )

    conversation_id = unknown_conversation_id()

    response = ChatResponse(
        conversation_id=conversation_id,
        response=ai_response,
        user_event=user_event,
        assistant_event=assistant_event,
    )

    assert response.conversation_id == conversation_id
    assert response.response is ai_response
    assert response.user_event is user_event
    assert response.assistant_event is assistant_event


def test_chat_response_rejects_extra_fields() -> None:
    """
    It should reject unexpected fields.
    """

    user_event = ConversationEventResponse.model_validate(
        ConversationEventFactory.build(
            role=MessageRoleEnum.USER,
        ),
    )

    assistant_event = ConversationEventResponse.model_validate(
        ConversationEventFactory.build(
            role=MessageRoleEnum.ASSISTANT,
        ),
    )

    with pytest.raises(ValidationError):
        ChatResponse(
            conversation_id="conv_123",
            response=AIResponse(
                content="Answer",
            ),
            user_event=user_event,
            assistant_event=assistant_event,
            unknown="value",
        )


def test_chat_stream_response_accepts_valid_response() -> None:
    """
    It should accept a valid stream response.
    """

    response = ChatStreamResponse(
        content="Hello",
        is_final=True,
        metadata={
            "provider": "groq",
        },
    )

    assert response.content == "Hello"
    assert response.is_final is True
    assert response.metadata == {
        "provider": "groq",
    }


def test_chat_stream_response_uses_default_metadata() -> None:
    """
    It should default metadata to an empty dictionary.
    """

    response = ChatStreamResponse(
        content="Hello",
    )

    assert response.metadata == {}
    assert response.is_final is False


def test_chat_stream_response_rejects_extra_fields() -> None:
    """
    It should reject unexpected fields.
    """

    with pytest.raises(ValidationError):
        ChatStreamResponse(
            content="Hello",
            unknown="value",
        )
