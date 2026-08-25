"""
Authentication API routes.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from src.api.dependencies.auth import get_authentication_service, get_current_user
from src.api.schemas.auth import LoginResponse, LogoutResponse, RefreshTokenRequest
from src.core.response import ApiResponse
from src.db.models.user import User
from src.services.auth import AuthenticationService

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/login",
    response_model=None,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user",
    description=("Authenticate a user using email and password " "and issue a JWT access token."),
)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: AuthenticationService = Depends(
        get_authentication_service,
    ),
) -> ApiResponse[LoginResponse]:
    """
    Authenticate a user and return an access token.
    """

    logger.debug(
        "Authentication attempt for user=%s",
        form_data.username,
    )

    try:
        user = await service.authenticate(
            email=form_data.username,
            password=form_data.password,
        )

        access_token, expires_in = service.create_access_token(
            user=user,
        )

    except ValueError as exc:
        logger.warning(
            "Authentication failed for user=%s: %s",
            form_data.username,
            exc,
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from exc

    except PermissionError as exc:
        logger.warning(
            "Authentication denied for inactive user=%s",
            form_data.username,
        )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    except Exception:
        logger.exception(
            "Unexpected authentication error for user=%s",
            form_data.username,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed",
        ) from None

    logger.info(
        "User authenticated successfully user_id=%s",
        user.id,
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.post(
    "/logout",
    response_model=None,
)
async def logout(
    current_user: User = Depends(get_current_user),
) -> ApiResponse[LogoutResponse]:
    """
    Log out the current client.

    JWT access tokens are stateless. The client is responsible
    for discarding the access token.

    Token revocation can be introduced later through a session
    or token blacklist mechanism.
    """

    logger.info(
        "Logout requested",
    )

    return ApiResponse(
        data=LogoutResponse(
            message="Successfully logged out",
        ),
        message="Logout successful.",
    )


@router.post(
    "/access-token",
    response_model=None,
)
async def access_token(
    request: RefreshTokenRequest,
    service: AuthenticationService = Depends(
        get_authentication_service,
    ),
) -> ApiResponse[LoginResponse]:
    """
    Exchange a refresh token for a new access token.
    """

    logger.debug(
        "Access token refresh requested",
    )

    try:
        access_token, expires_in = await service.refresh_access_token(
            refresh_token=request.refresh_token,
        )

    except ValueError as exc:
        logger.warning(
            "Access token refresh failed: %s",
            exc,
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from exc

    except Exception:
        logger.exception(
            "Unexpected error while refreshing access token",
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to refresh access token",
        ) from None

    logger.info(
        "Access token refreshed successfully",
    )

    return ApiResponse(
        data=LoginResponse(
            access_token=access_token,
            expires_in=expires_in,
        ),
        message="Access token refreshed successfully.",
    )
