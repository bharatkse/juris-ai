"""
Conversation API routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.conversation import get_conversation_service
from src.core.logger import get_logger
from src.core.response import ApiResponse
from src.core.types import ConversationId
from src.schemas.conversation import (
    ConversationListResponse,
    ConversationResponse,
    CreateConversationRequest,
)
from src.services.conversation import ConversationService

logger = get_logger(__name__)

router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation",
)
async def create_conversation(
    request: CreateConversationRequest,
    current_user=Depends(get_current_user),
    service: ConversationService = Depends(
        get_conversation_service,
    ),
) -> ApiResponse:
    """
    Create a new conversation.
    """

    logger.info(
        "Creating conversation.",
        extra={
            "operation": "create_conversation",
            "user_id": str(current_user.id),
        },
    )

    conversation = await service.create(request=request, user_id=current_user.id)

    return ApiResponse(
        data=ConversationResponse.model_validate(
            conversation,
            from_attributes=True,
        ),
        message="Conversation created successfully.",
        status_code=status.HTTP_201_CREATED,
    )


@router.get(
    "",
    summary="List conversations",
)
async def list_conversations(
    offset: int = 0,
    limit: int = 20,
    current_user=Depends(get_current_user),
    service: ConversationService = Depends(
        get_conversation_service,
    ),
) -> ApiResponse:
    """
    Retrieve paginated conversations for the authenticated user.
    """

    logger.info(
        "Listing conversations.",
        extra={
            "operation": "list_conversations",
            "user_id": str(current_user.id),
            "offset": offset,
            "limit": limit,
        },
    )

    conversations, total = await service.list(
        user_id=current_user.id,
        offset=offset,
        limit=limit,
    )

    return ApiResponse(
        data=ConversationListResponse(
            items=[
                ConversationResponse.model_validate(
                    conversation,
                    from_attributes=True,
                )
                for conversation in conversations
            ],
            pagination={
                "offset": offset,
                "limit": limit,
                "total": total,
                "has_more": offset + limit < total,
            },
        )
    )


@router.get(
    "/{conversation_id}",
    summary="Retrieve a conversation",
)
async def get_conversation(
    conversation_id: ConversationId,
    current_user=Depends(get_current_user),
    service: ConversationService = Depends(
        get_conversation_service,
    ),
) -> ApiResponse:
    """
    Retrieve a conversation.
    """

    logger.info(
        "Retrieving conversation.",
        extra={
            "operation": "get_conversation",
            "conversation_id": str(conversation_id),
            "user_id": str(current_user.id),
        },
    )

    conversation = await service.get_or_raise(
        conversation_id=conversation_id,
        user_id=current_user.id,
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
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive a conversation",
)
async def archive_conversation(
    conversation_id: ConversationId,
    current_user=Depends(get_current_user),
    service: ConversationService = Depends(
        get_conversation_service,
    ),
) -> ApiResponse:
    """
    Archive a conversation.
    """

    logger.info(
        "Archiving conversation.",
        extra={
            "operation": "archive_conversation",
            "conversation_id": str(conversation_id),
            "user_id": str(current_user.id),
        },
    )

    await service.archive(
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    return ApiResponse(
        message="Conversation archived successfully.",
        status_code=status.HTTP_204_NO_CONTENT,
    )
