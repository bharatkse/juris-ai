"""
Unit tests for AuthenticationService.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from jose import JWTError

from application.services.auth import AuthenticationService
from tests.factories.user import UserFactory


@pytest.mark.asyncio
async def test_authenticate_returns_user_for_valid_credentials(
    authentication_service: AuthenticationService,
    mock_user_repository: MagicMock,
    mock_password_service: MagicMock,
) -> None:
    """
    It should return the user when credentials are valid.
    """

    user = UserFactory.build(
        is_active=True,
    )

    mock_user_repository.get_by_email.return_value = user
    mock_password_service.verify.return_value = True

    result = await authentication_service.authenticate(
        email=user.email,
        password="correct-password",
    )

    assert result is user

    mock_user_repository.get_by_email.assert_awaited_once_with(
        user.email,
    )

    mock_password_service.verify.assert_called_once_with(
        "correct-password",
        user.password_hash,
    )


@pytest.mark.asyncio
async def test_authenticate_raises_when_user_does_not_exist(
    authentication_service: AuthenticationService,
    mock_user_repository: MagicMock,
    mock_password_service: MagicMock,
) -> None:
    """
    It should reject authentication when the user does not exist.
    """

    mock_user_repository.get_by_email.return_value = None

    with pytest.raises(
        ValueError,
        match="Invalid email or password",
    ):
        await authentication_service.authenticate(
            email="unknown@example.com",
            password="password",
        )

    mock_password_service.verify.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_raises_for_invalid_password(
    authentication_service: AuthenticationService,
    mock_user_repository: MagicMock,
    mock_password_service: MagicMock,
) -> None:
    """
    It should reject authentication when the password is invalid.
    """

    user = UserFactory.build(
        is_active=True,
    )

    mock_user_repository.get_by_email.return_value = user
    mock_password_service.verify.return_value = False

    with pytest.raises(
        ValueError,
        match="Invalid email or password",
    ):
        await authentication_service.authenticate(
            email=user.email,
            password="wrong-password",
        )

    mock_password_service.verify.assert_called_once_with(
        "wrong-password",
        user.password_hash,
    )


@pytest.mark.asyncio
async def test_authenticate_raises_for_inactive_user(
    authentication_service: AuthenticationService,
    mock_user_repository: MagicMock,
    mock_password_service: MagicMock,
) -> None:
    """
    It should reject authentication for an inactive user.
    """

    user = UserFactory.build(
        is_active=False,
    )

    mock_user_repository.get_by_email.return_value = user
    mock_password_service.verify.return_value = True

    with pytest.raises(
        PermissionError,
        match="User account is inactive",
    ):
        await authentication_service.authenticate(
            email=user.email,
            password="correct-password",
        )

    mock_password_service.verify.assert_called_once_with(
        "correct-password",
        user.password_hash,
    )


@pytest.mark.asyncio
async def test_authenticate_raises_when_password_verification_fails(
    authentication_service: AuthenticationService,
    mock_user_repository: MagicMock,
    mock_password_service: MagicMock,
) -> None:
    """
    It should convert unexpected password verification failures
    into an authentication error.
    """

    user = UserFactory.build(
        is_active=True,
    )

    mock_user_repository.get_by_email.return_value = user
    mock_password_service.verify.side_effect = RuntimeError(
        "password backend unavailable",
    )

    with pytest.raises(
        ValueError,
        match="Unable to authenticate user",
    ):
        await authentication_service.authenticate(
            email=user.email,
            password="password",
        )

    mock_password_service.verify.assert_called_once_with(
        "password",
        user.password_hash,
    )


def test_create_access_token_returns_token_and_expiry(
    authentication_service: AuthenticationService,
) -> None:
    """
    It should create and return an access token.
    """

    user = UserFactory.build(
        is_active=True,
    )

    with patch(
        "application.services.auth.create_access_token",
        return_value=("access-token", 3600),
    ) as create_token:
        token, expires_in = authentication_service.create_access_token(
            user=user,
        )

    assert token == "access-token"
    assert expires_in == 3600

    create_token.assert_called_once_with(
        user,
    )


def test_create_access_token_propagates_token_creation_error(
    authentication_service: AuthenticationService,
) -> None:
    """
    It should propagate unexpected token creation failures.
    """

    user = UserFactory.build(
        is_active=True,
    )

    with patch(
        "application.services.auth.create_access_token",
        side_effect=RuntimeError("JWT configuration error"),
    ):
        with pytest.raises(
            RuntimeError,
            match="JWT configuration error",
        ):
            authentication_service.create_access_token(
                user=user,
            )


@pytest.mark.asyncio
async def test_refresh_access_token_returns_new_access_token(
    authentication_service: AuthenticationService,
    mock_user_repository: MagicMock,
) -> None:
    """
    It should create a new access token from a valid refresh token.
    """

    user = UserFactory.build(
        is_active=True,
    )

    mock_user_repository.get.return_value = user

    payload = {
        "sub": user.id,
        "type": "refresh",
    }

    with (
        patch(
            "application.services.auth.decode_token",
            return_value=payload,
        ) as decode_token,
        patch(
            "application.services.auth.is_token_type",
            return_value=True,
        ) as is_token_type,
        patch(
            "application.services.auth.get_subject",
            return_value=user.id,
        ) as get_subject,
        patch(
            "application.services.auth.create_access_token",
            return_value=("new-access-token", 3600),
        ) as create_token,
    ):
        token, expires_in = await authentication_service.refresh_access_token(
            refresh_token="refresh-token",
        )

    assert token == "new-access-token"
    assert expires_in == 3600

    decode_token.assert_called_once_with(
        "refresh-token",
    )

    is_token_type.assert_called_once_with(
        payload,
        "refresh",
    )

    get_subject.assert_called_once_with(
        payload,
    )

    mock_user_repository.get.assert_awaited_once_with(
        user.id,
    )

    create_token.assert_called_once_with(
        user,
    )


@pytest.mark.asyncio
async def test_refresh_access_token_raises_for_invalid_token(
    authentication_service: AuthenticationService,
) -> None:
    """
    It should reject an invalid refresh token.
    """

    with patch(
        "application.services.auth.decode_token",
        side_effect=JWTError("Invalid token"),
    ):
        with pytest.raises(
            ValueError,
            match="Invalid refresh token",
        ):
            await authentication_service.refresh_access_token(
                refresh_token="invalid-token",
            )


@pytest.mark.asyncio
async def test_refresh_access_token_raises_for_invalid_token_type(
    authentication_service: AuthenticationService,
) -> None:
    """
    It should reject a token that is not a refresh token.
    """

    payload = {
        "sub": "user_123",
        "type": "access",
    }

    with (
        patch(
            "application.services.auth.decode_token",
            return_value=payload,
        ),
        patch(
            "application.services.auth.is_token_type",
            return_value=False,
        ),
    ):
        with pytest.raises(
            ValueError,
            match="Invalid token type",
        ):
            await authentication_service.refresh_access_token(
                refresh_token="access-token",
            )


@pytest.mark.asyncio
async def test_refresh_access_token_raises_when_subject_missing(
    authentication_service: AuthenticationService,
) -> None:
    """
    It should reject a refresh token without a subject.
    """

    payload = {
        "type": "refresh",
    }

    with (
        patch(
            "application.services.auth.decode_token",
            return_value=payload,
        ),
        patch(
            "application.services.auth.is_token_type",
            return_value=True,
        ),
        patch(
            "application.services.auth.get_subject",
            return_value=None,
        ),
    ):
        with pytest.raises(
            ValueError,
            match="Invalid refresh token",
        ):
            await authentication_service.refresh_access_token(
                refresh_token="refresh-token",
            )


@pytest.mark.asyncio
async def test_refresh_access_token_raises_when_user_does_not_exist(
    authentication_service: AuthenticationService,
    mock_user_repository: MagicMock,
) -> None:
    """
    It should reject a refresh token when the user no longer exists.
    """

    user_id = "user_" + "a" * 32

    mock_user_repository.get.return_value = None

    payload = {
        "sub": user_id,
        "type": "refresh",
    }

    with (
        patch(
            "application.services.auth.decode_token",
            return_value=payload,
        ),
        patch(
            "application.services.auth.is_token_type",
            return_value=True,
        ),
        patch(
            "application.services.auth.get_subject",
            return_value=user_id,
        ),
    ):
        with pytest.raises(
            ValueError,
            match="User is not available",
        ):
            await authentication_service.refresh_access_token(
                refresh_token="refresh-token",
            )

    mock_user_repository.get.assert_awaited_once_with(
        user_id,
    )


@pytest.mark.asyncio
async def test_refresh_access_token_raises_for_inactive_user(
    authentication_service: AuthenticationService,
    mock_user_repository: MagicMock,
) -> None:
    """
    It should reject a refresh token for an inactive user.
    """

    user = UserFactory.build(
        is_active=False,
    )

    mock_user_repository.get.return_value = user

    payload = {
        "sub": user.id,
        "type": "refresh",
    }

    with (
        patch(
            "application.services.auth.decode_token",
            return_value=payload,
        ),
        patch(
            "application.services.auth.is_token_type",
            return_value=True,
        ),
        patch(
            "application.services.auth.get_subject",
            return_value=user.id,
        ),
    ):
        with pytest.raises(
            ValueError,
            match="User is not available",
        ):
            await authentication_service.refresh_access_token(
                refresh_token="refresh-token",
            )


@pytest.mark.asyncio
async def test_refresh_access_token_propagates_token_creation_error(
    authentication_service: AuthenticationService,
    mock_user_repository: MagicMock,
) -> None:
    """
    It should propagate an unexpected access token creation failure.
    """

    user = UserFactory.build(
        is_active=True,
    )

    mock_user_repository.get.return_value = user

    payload = {
        "sub": user.id,
        "type": "refresh",
    }

    with (
        patch(
            "application.services.auth.decode_token",
            return_value=payload,
        ),
        patch(
            "application.services.auth.is_token_type",
            return_value=True,
        ),
        patch(
            "application.services.auth.get_subject",
            return_value=user.id,
        ),
        patch(
            "application.services.auth.create_access_token",
            side_effect=RuntimeError("JWT configuration error"),
        ),
    ):
        with pytest.raises(
            RuntimeError,
            match="JWT configuration error",
        ):
            await authentication_service.refresh_access_token(
                refresh_token="refresh-token",
            )
