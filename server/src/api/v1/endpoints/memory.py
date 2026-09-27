"""
User memory API routes.

Self-service transparency and control over the durable facts the
assistant has saved about the authenticated user. Every route acts only
on the caller's own memories: the user id always comes from the access
token, never from the path or body.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status

from adapters.observability.logger import get_logger
from api.dependencies.auth import get_current_user
from api.dependencies.user_memory import get_user_memory_service
from api.schemas.memory import (
    MemoryItemResponse,
    MemoryListResponse,
    MemorySettingsResponse,
    UpdateMemorySettingsRequest,
)
from api.utilities.api_response import ApiResponse
from application.services.user_memory import UserMemoryService
from core.constants import MAX_PAGE_SIZE
from core.types import UserMemoryId

logger = get_logger(__name__)

router = APIRouter(
    prefix="/memory",
    tags=["Memory"],
)


@router.get(
    "/settings",
    summary="Get the long-term memory setting",
)
async def get_memory_settings(
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """
    Whether long-term memory is on for the authenticated user. It is off
    until the user turns it on.
    """

    return ApiResponse(
        data=MemorySettingsResponse(
            enabled=bool(current_user.memory_enabled),
            consent_updated_at=current_user.memory_consent_updated_at,
        ),
    )


@router.put(
    "/settings",
    summary="Turn long-term memory on or off",
)
async def update_memory_settings(
    request: UpdateMemorySettingsRequest,
    current_user=Depends(get_current_user),
    service: UserMemoryService = Depends(
        get_user_memory_service,
    ),
) -> ApiResponse:
    """
    Turn long-term memory on or off.

    Turning it OFF permanently deletes every memory saved so far, in the
    same transaction as the change. This cannot be undone.
    """

    user = await service.set_consent(
        user_id=current_user.id,
        enabled=request.enabled,
    )

    return ApiResponse(
        data=MemorySettingsResponse(
            enabled=bool(user.memory_enabled),
            consent_updated_at=user.memory_consent_updated_at,
        ),
        message=(
            "Memory turned on."
            if user.memory_enabled
            else "Memory turned off and all saved memories deleted."
        ),
    )


@router.get(
    "/items",
    summary="List saved memories",
)
async def list_memories(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=MAX_PAGE_SIZE),
    current_user=Depends(get_current_user),
    service: UserMemoryService = Depends(
        get_user_memory_service,
    ),
) -> ApiResponse:
    """
    The authenticated user's saved memories, newest first. Memories past
    their retention window are deleted before the list is built.
    """

    memories, total = await service.list_memories(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )

    return ApiResponse(
        data=MemoryListResponse(
            items=[
                MemoryItemResponse.model_validate(
                    memory,
                    from_attributes=True,
                )
                for memory in memories
            ],
            pagination={
                "offset": offset,
                "limit": limit,
                "total": total,
                "has_more": offset + limit < total,
            },
        ),
    )


@router.get(
    "/items/{memory_id}",
    summary="Retrieve a saved memory",
)
async def get_memory(
    memory_id: UserMemoryId,
    current_user=Depends(get_current_user),
    service: UserMemoryService = Depends(
        get_user_memory_service,
    ),
) -> ApiResponse:
    """
    One of the authenticated user's saved memories. Another user's id,
    an expired memory and a replaced memory are all simply "not found".
    """

    memory = await service.get_memory(
        user_id=current_user.id,
        memory_id=memory_id,
    )

    return ApiResponse(
        data=MemoryItemResponse.model_validate(
            memory,
            from_attributes=True,
        ),
    )


@router.delete(
    "/items/{memory_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a saved memory",
)
async def delete_memory(
    memory_id: UserMemoryId,
    current_user=Depends(get_current_user),
    service: UserMemoryService = Depends(
        get_user_memory_service,
    ),
) -> Response:
    """
    Permanently delete one of the authenticated user's saved memories.
    """

    await service.delete_memory(
        user_id=current_user.id,
        memory_id=memory_id,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
