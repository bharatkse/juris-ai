"""
User API routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from src.api.dependencies.user import get_user_service
from src.core.response import ApiResponse
from src.core.types import UserId
from src.schemas.user import CreateUserRequest, UpdateUserRequest, UserResponse
from src.services.user import UserService

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
)
async def create_user(
    request: CreateUserRequest,
    service: UserService = Depends(get_user_service),
) -> ApiResponse:
    """
    Create a new user.
    """

    user = await service.create(request)

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
    summary="Get user details",
)
async def get_user(
    user_id: UserId,
    service: UserService = Depends(get_user_service),
) -> ApiResponse:
    """
    Retrieve user details.
    """

    user = await service.get(user_id)

    return ApiResponse(
        data=UserResponse.model_validate(
            user,
            from_attributes=True,
        ),
        message="User retrieved successfully.",
    )


@router.patch(
    "/{user_id}",
    summary="Update user profile",
)
async def update_user(
    user_id: UserId,
    request: UpdateUserRequest,
    service: UserService = Depends(get_user_service),
) -> ApiResponse:
    """
    Update a user profile.
    """

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
