"""
User API routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from adapters.observability.logger import get_logger
from api.dependencies.auth import get_current_user
from api.dependencies.user import get_user_service
from api.schemas.user import (
    RegisterNewUserRequest,
    UpdateUserProfileRequest,
    UserResponse,
)
from api.utilities.api_response import ApiResponse
from application.services.user import UserService
from core.types import UserId

logger = get_logger(__name__)

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


def ensure_profile_owner(
    *,
    user_id: UserId,
    current_user_id: UserId,
) -> None:
    """
    Restrict profile reads and updates to the authenticated user.
    """

    if str(user_id) != str(current_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only access your own profile",
        )


@router.post(
    "",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def user_registration(
    request: RegisterNewUserRequest,
    service: UserService = Depends(
        get_user_service,
    ),
) -> ApiResponse:
    """
    Registering  a new user.
    """

    logger.info(
        "Registering  a new user.",
        extra={
            "operation": "user_registration",
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
        message="User registered successfully.",
        status_code=status.HTTP_201_CREATED,
    )


@router.get(
    "/{user_id}",
    response_model=None,
    summary="Retrieve a user details",
)
async def get_user_details(
    user_id: UserId,
    current_user=Depends(get_current_user),
    service: UserService = Depends(
        get_user_service,
    ),
) -> ApiResponse:
    """
    Retrieve a user details.
    """

    ensure_profile_owner(
        user_id=user_id,
        current_user_id=current_user.id,
    )

    logger.info(
        "Retrieving user details.",
        extra={
            "operation": "get_user_details",
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
        message="User details retrieved successfully.",
    )


@router.patch(
    "/{user_id}",
    response_model=None,
    summary="Update a user profile",
)
async def update_user_profile(
    user_id: UserId,
    request: UpdateUserProfileRequest,
    current_user=Depends(get_current_user),
    service: UserService = Depends(
        get_user_service,
    ),
) -> ApiResponse:
    """
    Update a user profile.
    """

    ensure_profile_owner(
        user_id=user_id,
        current_user_id=current_user.id,
    )

    logger.info(
        "Updating user profile.",
        extra={
            "operation": "update_user_profile",
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
        message="User profile updated successfully.",
    )
