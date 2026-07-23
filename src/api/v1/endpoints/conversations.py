"""
Conversation API routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies.conversation import get_conversation_service
from src.core.response import ApiResponse
from src.core.types import ConversationId
from src.schemas.conversation import ConversationResponse, CreateConversationRequest
from src.services.conversation import ConversationService

router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)


@router.post(
    "",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation",
)
async def create_conversation(
    request: CreateConversationRequest,
    service: ConversationService = Depends(get_conversation_service),
) -> ApiResponse:
    """
    Create a new conversation.
    """

    conversation = await service.create(request)

    return ApiResponse(
        data=ConversationResponse.model_validate(
            conversation,
            from_attributes=True,
        ),
        message="Conversation created successfully.",
        status_code=status.HTTP_201_CREATED,
    )


@router.get(
    "/{conversation_id}",
    response_model=None,
    summary="Retrieve a conversation",
)
async def get_conversation(
    conversation_id: ConversationId,
    service: ConversationService = Depends(get_conversation_service),
) -> ApiResponse:
    """
    Retrieve a conversation by its identifier.
    """

    conversation = await service.get(conversation_id)

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    return ApiResponse(
        data=ConversationResponse.model_validate(
            conversation,
            from_attributes=True,
        ),
        message="Conversation retrieved successfully.",
    )


@router.delete(
    "/{conversation_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive a conversation",
)
async def archive_conversation(
    conversation_id: ConversationId,
    service: ConversationService = Depends(get_conversation_service),
) -> ApiResponse:
    """
    Archive a conversation.
    """

    conversation = await service.get(conversation_id)

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    await service.archive(conversation)

    return ApiResponse(
        message="Conversation archived successfully.",
        status_code=status.HTTP_204_NO_CONTENT,
    )
