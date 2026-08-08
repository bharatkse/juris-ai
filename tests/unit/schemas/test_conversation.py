"""
Unit tests for conversation schemas.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.schemas.conversation import ConversationResponse, CreateConversationRequest
from tests.builders.schemas import build_create_conversation_request
from tests.factories.conversation import ConversationFactory


def test_create_conversation_request_accepts_valid_request() -> None:
    """
    It should accept a valid request.
    """

    request = build_create_conversation_request()

    assert isinstance(
        request,
        CreateConversationRequest,
    )


def test_create_conversation_request_accepts_title() -> None:
    """
    It should accept a custom title.
    """

    request = build_create_conversation_request(
        title="Legal Advice",
    )

    assert request.title == "Legal Advice"


def test_create_conversation_request_accepts_none_title() -> None:
    """
    It should allow the title to be omitted.
    """

    request = build_create_conversation_request(
        title=None,
    )

    assert request.title is None


def test_create_conversation_request_rejects_extra_fields() -> None:
    """
    It should reject unexpected fields.
    """

    with pytest.raises(
        ValidationError,
    ):
        CreateConversationRequest(
            title="Legal",
            unknown="value",
        )


def test_conversation_response_can_be_created_from_conversation() -> None:
    """
    It should create a response from a conversation entity.
    """

    conversation = ConversationFactory.build()

    response = ConversationResponse.model_validate(
        conversation,
    )

    assert response.id == conversation.id
    assert response.user_id == conversation.user_id
    assert response.title == conversation.title
    assert response.is_active == conversation.is_active
    assert response.created_at == conversation.created_at
    assert response.updated_at == conversation.updated_at


def test_conversation_response_model_dump() -> None:
    """
    It should serialize the response.
    """

    conversation = ConversationFactory.build()

    response = ConversationResponse.model_validate(
        conversation,
    )

    data = response.model_dump()

    assert data["id"] == conversation.id
    assert data["user_id"] == conversation.user_id
    assert data["title"] == conversation.title
    assert data["is_active"] == conversation.is_active


def test_conversation_response_rejects_extra_fields() -> None:
    """
    It should reject unexpected fields.
    """

    with pytest.raises(
        ValidationError,
    ):
        ConversationResponse(
            id="conv_123",
            user_id="user_123",
            title="Legal",
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            unknown="value",
        )
