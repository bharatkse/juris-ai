"""
Chat API routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.api.dependencies.chat import get_chat_service
from src.core.response import ApiResponse
from src.schemas.chat import ChatRequest, ChatResponse, ConversationEventResponse
from src.services.chat import ChatService

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post(
    "",
    summary="Chat with JurisAI",
    status_code=status.HTTP_200_OK,
)
async def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ApiResponse:
    """
    Send a message to JurisAI.

    The request is stored as a user event,
    processed by the AI agent, and the generated
    response is stored as an assistant event.
    """

    result = await service.chat(
        conversation_id=request.conversation_id,
        message=request.message,
    )

    return ApiResponse(
        success=True,
        data=ChatResponse(
            conversation_id=result.conversation.id,
            user_event=ConversationEventResponse.model_validate(
                result.user_event,
                from_attributes=True,
            ),
            assistant_event=ConversationEventResponse.model_validate(
                result.assistant_event,
                from_attributes=True,
            ),
        ),
        status_code=status.HTTP_200_OK,
    )
