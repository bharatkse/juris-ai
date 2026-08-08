"""
User API routes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, status

from src.api.dependencies.user import get_user_service
from src.core.logger import get_logger
from src.core.response import ApiResponse
from src.schemas.user import CreateUserRequest, UpdateUserRequest, UserResponse
from src.services.user import UserService

if TYPE_CHECKING:
    from src.core.types import UserId

logger = get_logger(__name__)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.post(
    "",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
)
async def create_user(
    request: CreateUserRequest,
    service: UserService = Depends(
        get_user_service,
    ),
) -> ApiResponse:
    """
    Create a new user.
    """

    logger.info(
        "Creating user.",
        extra={
            "operation": "create_user",
            "email": request.email,
        },
    )

    user = await service.create(
        request=request,
    )

    return ApiResponse(
        data=UserResponse.model_validate(
            user,
            from_attributes=True,
        ),
        message="User created successfully.",
        status_code=status.HTTP_201_CREATED,
    )


@router.get(
    "/{user_id}",
    response_model=None,
    summary="Retrieve a user",
)
async def get_user(
    user_id: UserId,
    service: UserService = Depends(
        get_user_service,
    ),
) -> ApiResponse:
    """
    Retrieve a user.
    """

    logger.info(
        "Retrieving user.",
        extra={
            "operation": "get_user",
            "user_id": str(user_id),
        },
    )

    user = await service.get_or_raise(
        user_id=user_id,
    )

    return ApiResponse(
        data=UserResponse.model_validate(
            user,
            from_attributes=True,
        ),
        message="User retrieved successfully.",
    )


@router.patch(
    "/{user_id}",
    response_model=None,
    summary="Update a user",
)
async def update_user(
    user_id: UserId,
    request: UpdateUserRequest,
    service: UserService = Depends(
        get_user_service,
    ),
) -> ApiResponse:
    """
    Update a user.
    """

    logger.info(
        "Updating user.",
        extra={
            "operation": "update_user",
            "user_id": str(user_id),
        },
    )

    user = await service.update(
        user_id=user_id,
        request=request,
    )

    return ApiResponse(
        data=UserResponse.model_validate(
            user,
            from_attributes=True,
        ),
        message="User updated successfully.",
    )
