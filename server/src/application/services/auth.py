"""
Authentication service.
"""

from __future__ import annotations

import logging

from jose import JWTError

from adapters.persistence.sqlalchemy.models.user import User
from adapters.persistence.sqlalchemy.repositories.user import UserRepository
from adapters.security.jwt import (
    create_access_token,
    decode_token,
    get_subject,
    is_token_type,
)
from adapters.security.password import PasswordService

logger = logging.getLogger(__name__)


class AuthenticationService:
    """
    Application service for authentication operations.
    """

    def __init__(
        self, *, user_repository: UserRepository, password_service: PasswordService
    ) -> None:
        self._user_repository = user_repository
        self._password_service = password_service

    async def authenticate(
        self,
        *,
        email: str,
        password: str,
    ) -> User:
        """
        Authenticate a user using email and password.
        """

        logger.debug(
            "Authenticating user email=%s",
            email,
        )

        user = await self._user_repository.get_by_email(
            email,
        )

        if user is None:
            logger.warning(
                "Authentication failed: user not found email=%s",
                email,
            )

            raise ValueError(
                "Invalid email or password",
            )

        try:
            password_valid = self._password_service.verify(
                password,
                user.password_hash,
            )
        except Exception:
            logger.exception(
                "Password verification failed unexpectedly user_id=%s",
                user.id,
            )

            raise ValueError(
                "Unable to authenticate user",
            ) from None

        if not password_valid:
            logger.warning(
                "Authentication failed: invalid password user_id=%s",
                user.id,
            )

            raise ValueError(
                "Invalid email or password",
            )

        if not user.is_active:
            logger.warning(
                "Authentication denied: inactive user user_id=%s",
                user.id,
            )

            raise PermissionError(
                "User account is inactive",
            )

        logger.info(
            "User authenticated successfully user_id=%s",
            user.id,
        )

        return user

    def create_access_token(
        self,
        *,
        user: User,
    ) -> tuple[str, int]:
        """
        Create an access token for an authenticated user.
        """

        try:
            token, expires_in = create_access_token(
                user,
            )
        except Exception:
            logger.exception(
                "Failed to create access token user_id=%s",
                user.id,
            )

            raise

        logger.debug(
            "Access token created user_id=%s expires_in=%s",
            user.id,
            expires_in,
        )

        return token, expires_in

    async def refresh_access_token(
        self,
        *,
        refresh_token: str,
    ) -> tuple[str, int]:
        """
        Validate a refresh token and create a new access token.
        """

        logger.debug(
            "Refreshing access token",
        )

        try:
            payload = decode_token(
                refresh_token,
            )
        except JWTError:
            logger.warning(
                "Access token refresh failed: invalid or expired refresh token",
            )

            raise ValueError(
                "Invalid refresh token",
            ) from None

        if not is_token_type(
            payload,
            "refresh",
        ):
            logger.warning(
                "Access token refresh failed: invalid token type",
            )

            raise ValueError(
                "Invalid token type",
            )

        user_id = get_subject(
            payload,
        )

        if not user_id:
            logger.warning(
                "Access token refresh failed: token subject missing",
            )

            raise ValueError(
                "Invalid refresh token",
            )

        user = await self._user_repository.get(
            user_id,
        )

        if user is None:
            logger.warning(
                "Access token refresh failed: user not found user_id=%s",
                user_id,
            )

            raise ValueError(
                "User is not available",
            )

        if not user.is_active:
            logger.warning(
                "Access token refresh denied: inactive user user_id=%s",
                user.id,
            )

            raise ValueError(
                "User is not available",
            )

        try:
            token, expires_in = create_access_token(
                user,
            )
        except Exception:
            logger.exception(
                "Failed to create refreshed access token user_id=%s",
                user.id,
            )

            raise

        logger.info(
            "Access token refreshed successfully user_id=%s",
            user.id,
        )

        return token, expires_in
