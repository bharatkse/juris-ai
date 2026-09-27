"""
Conversation API routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from adapters.observability.logger import get_logger
from api.dependencies.auth import get_current_user
from api.dependencies.conversation import (
    get_conversation_event_service,
    get_conversation_service,
)
from api.schemas.chat import ConversationEventListResponse, ConversationEventResponse
from api.schemas.conversation import (
    ConversationListResponse,
    ConversationResponse,
    CreateConversationRequest,
    UpdateConversationMemoryRequest,
    UpdateConversationRequest,
)
from api.utilities.api_response import ApiResponse
from application.services.conversation import ConversationService
from application.services.conversation_event import ConversationEventService
from core.types import ConversationId

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


@router.patch(
    "/{conversation_id}",
    summary="Rename a conversation",
)
async def update_conversation(
    conversation_id: ConversationId,
    request: UpdateConversationRequest,
    current_user=Depends(get_current_user),
    service: ConversationService = Depends(
        get_conversation_service,
    ),
) -> ApiResponse:
    """
    Update an authenticated user's conversation title.
    """

    conversation = await service.update_title(
        conversation_id=conversation_id,
        user_id=current_user.id,
        title=request.title,
    )

    return ApiResponse(
        data=ConversationResponse.model_validate(
            conversation,
            from_attributes=True,
        ),
        message="Conversation updated successfully.",
    )


@router.get(
    "/{conversation_id}/events",
    summary="List conversation events",
)
async def list_conversation_events(
    conversation_id: ConversationId,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    current_user=Depends(get_current_user),
    conversation_service: ConversationService = Depends(
        get_conversation_service,
    ),
    event_service: ConversationEventService = Depends(
        get_conversation_event_service,
    ),
) -> ApiResponse:
    """
    Retrieve a chronological, paginated transcript.

    Conversation ownership is checked before events are queried.
    """

    await conversation_service.get_or_raise(
        conversation_id=conversation_id,
        user_id=current_user.id,
    )

    events, total = await event_service.list_page(
        conversation_id=conversation_id,
        offset=offset,
        limit=limit,
    )

    return ApiResponse(
        data=ConversationEventListResponse(
            items=[
                ConversationEventResponse.model_validate(
                    event,
                    from_attributes=True,
                )
                for event in events
            ],
            pagination={
                "offset": offset,
                "limit": limit,
                "total": total,
                "has_more": offset + limit < total,
            },
        )
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


@router.put(
    "/{conversation_id}/memory",
    summary='Turn "don\'t remember this" on or off for a conversation',
)
async def update_conversation_memory(
    conversation_id: ConversationId,
    request: UpdateConversationMemoryRequest,
    current_user=Depends(get_current_user),
    service: ConversationService = Depends(
        get_conversation_service,
    ),
) -> ApiResponse:
    """
    Stop (or resume) saving what is said in this conversation to
    long-term memory.

    Forward-only: turning it on does NOT delete facts already saved from
    earlier messages. To remove those, delete them from the memory list
    or turn memory off, which deletes everything.
    """

    conversation = await service.set_memory_disabled(
        conversation_id=conversation_id,
        user_id=current_user.id,
        disabled=request.memory_disabled,
    )

    return ApiResponse(
        data=ConversationResponse.model_validate(
            conversation,
            from_attributes=True,
        ),
        message=(
            "New messages in this conversation will not be saved to memory. "
            "Anything already saved is unchanged."
            if conversation.memory_disabled
            else "Memory is allowed again for this conversation."
        ),
    )
