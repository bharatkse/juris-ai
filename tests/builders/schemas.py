from datetime import date

from src.core.enums import Gender
from src.schemas.chat import ChatRequest
from src.schemas.conversation import CreateConversationRequest
from src.schemas.user import CreateUserRequest, UpdateUserRequest
from tests.helpers.identifiers import unknown_conversation_id, unknown_user_id


def build_create_user_request(
    **kwargs,
) -> CreateUserRequest:
    data = {
        "email": "john@example.com",
        "password": "Password@123",
        "confirm_password": "Password@123",
        "first_name": "John",
        "last_name": "Doe",
        "gender": Gender.MALE,
        "phone_number": "9876543210",
        "date_of_birth": date(1995, 1, 1),
    }

    data.update(kwargs)

    return CreateUserRequest(
        **data,
    )


def build_update_user_request(
    **kwargs,
) -> UpdateUserRequest:
    data = {
        "first_name": None,
        "last_name": None,
        "gender": None,
        "phone_number": None,
        "date_of_birth": None,
    }

    data.update(kwargs)

    return UpdateUserRequest(
        **data,
    )


def build_create_conversation_request(
    **kwargs,
) -> CreateConversationRequest:
    """
    Build a CreateConversationRequest.
    """

    data = {
        "user_id": unknown_user_id(),
        "title": "New Conversation",
    }

    data.update(kwargs)

    return CreateConversationRequest(
        **data,
    )


def build_chat_request(
    **kwargs,
) -> ChatRequest:
    """
    Build a ChatRequest.
    """

    data = {
        "conversation_id": unknown_conversation_id(),
        "message": "Hello",
    }

    data.update(kwargs)

    return ChatRequest(
        **data,
    )
