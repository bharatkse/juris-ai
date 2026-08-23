"""
Builders for request and response schemas used in tests.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from src.api.schemas.chat import (
    AIResponse,
    ChatRequest,
    ChatResponse,
    ChatStreamResponse,
    ConversationEventResponse,
)
from src.api.schemas.conversation import ConversationResponse, CreateConversationRequest
from src.api.schemas.user import (
    RegisterNewUserRequest,
    UpdateUserProfileRequest,
    UserResponse,
)
from src.core.enums import GenderEnum, MessageRoleEnum
from src.core.schemas.response import (
    AIUsageModel,
    ApiResponseModel,
    ErrorDetailModel,
    MetadataModel,
    PaginationModel,
)
from tests.factories.conversation import ConversationFactory
from tests.factories.conversation_event import ConversationEventFactory
from tests.factories.user import UserFactory
from tests.helpers.identifiers import unknown_conversation_id


def build_create_user_request(
    **kwargs: Any,
) -> RegisterNewUserRequest:
    data = {
        "email": "john@example.com",
        "password": "Password@123",
        "confirm_password": "Password@123",
        "first_name": "John",
        "last_name": "Doe",
        "gender": GenderEnum.MALE,
        "phone_number": "9876543210",
        "date_of_birth": date(1995, 1, 1),
    }
    data.update(kwargs)

    return RegisterNewUserRequest(**data)


def build_update_user_request(
    **kwargs: Any,
) -> UpdateUserProfileRequest:
    data = {
        "first_name": None,
        "last_name": None,
        "gender": None,
        "phone_number": None,
        "date_of_birth": None,
    }
    data.update(kwargs)

    return UpdateUserProfileRequest(**data)


def build_create_conversation_request(
    *,
    title: str | None = "Legal",
    **kwargs,
) -> CreateConversationRequest:
    data = {
        "title": title,
    }

    data.update(kwargs)

    return CreateConversationRequest(
        **data,
    )


def build_chat_request(
    **kwargs: Any,
) -> ChatRequest:
    data = {
        "conversation_id": unknown_conversation_id(),
        "message": "Hello",
    }
    data.update(kwargs)

    return ChatRequest(**data)


def build_conversation_response(
    **kwargs: Any,
) -> ConversationResponse:
    conversation = ConversationFactory.build()

    data = {
        "id": conversation.id,
        "user_id": conversation.user_id,
        "title": conversation.title,
        "is_active": conversation.is_active,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
    }
    data.update(kwargs)

    return ConversationResponse(**data)


def build_user_response(
    **kwargs: Any,
) -> UserResponse:
    user = UserFactory.build()

    data = {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "gender": user.gender,
        "phone_number": user.phone_number,
        "date_of_birth": user.date_of_birth,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }
    data.update(kwargs)

    return UserResponse(**data)


def build_conversation_event_response(
    **kwargs: Any,
) -> ConversationEventResponse:
    event = ConversationEventFactory.build()

    data = {
        "id": event.id,
        "conversation_id": event.conversation_id,
        "parent_event_id": event.parent_event_id,
        "role": event.role,
        "content": event.content,
        "metadata": event.event_metadata or {},
        "created_at": event.created_at,
    }
    data.update(kwargs)

    return ConversationEventResponse(**data)


def build_ai_response(
    **kwargs: Any,
) -> AIResponse:
    data = {
        "message": "Hello!",
        "metadata": {},
    }
    data.update(kwargs)

    return AIResponse(**data)


def build_chat_response(
    **kwargs: Any,
) -> ChatResponse:
    user_event = build_conversation_event_response(
        role=MessageRoleEnum.USER,
        content="Hello",
    )

    assistant_event = build_conversation_event_response(
        role=MessageRoleEnum.ASSISTANT,
        content="Hi!",
    )

    data = {
        "conversation_id": user_event.conversation_id,
        "response": build_ai_response(),
        "user_event": user_event,
        "assistant_event": assistant_event,
    }
    data.update(kwargs)

    return ChatResponse(**data)


def build_chat_stream_response(
    **kwargs: Any,
) -> ChatStreamResponse:
    data = {
        "content": "Hello",
        "is_final": False,
        "metadata": {},
    }
    data.update(kwargs)

    return ChatStreamResponse(**data)


def build_ai_usage_model(
    **kwargs: Any,
) -> AIUsageModel:
    data = {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "agent": None,
        "workflow": None,
        "latency_ms": 100,
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30,
        "tool_calls": 0,
    }
    data.update(kwargs)

    return AIUsageModel(**data)


def build_metadata_model(
    **kwargs: Any,
) -> MetadataModel:
    data = {
        "request_id": "req_123",
        "trace_id": "trace_123",
        "timestamp": datetime.now(UTC),
        "ai": None,
    }
    data.update(kwargs)

    return MetadataModel(**data)


def build_error_detail_model(
    **kwargs: Any,
) -> ErrorDetailModel:
    data = {
        "code": "NOT_FOUND",
        "message": "Resource not found.",
        "details": None,
    }
    data.update(kwargs)

    return ErrorDetailModel(**data)


def build_pagination_model(
    **kwargs: Any,
) -> PaginationModel:
    data = {
        "total": 0,
        "offset": 0,
        "limit": 20,
        "has_more": False,
    }
    data.update(kwargs)

    return PaginationModel(**data)


def build_api_response(
    **kwargs: Any,
) -> ApiResponseModel:
    data = {
        "success": True,
        "data": None,
        "error": None,
        "metadata": build_metadata_model(),
        "message": None,
    }
    data.update(kwargs)

    return ApiResponseModel(**data)
