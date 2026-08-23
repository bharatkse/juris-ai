"""
Unit tests for Authentication API routes.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from src.api.schemas.auth import RefreshTokenRequest
from src.api.v1.endpoints.auth import access_token, login, logout
from src.core.response import ApiResponse
from tests.factories.user import UserFactory


def build_form_data(
    *,
    username: str = "user@example.com",
    password: str = "password",
) -> OAuth2PasswordRequestForm:
    """
    Build OAuth2 password form data for route unit tests.
    """

    return OAuth2PasswordRequestForm(
        username=username,
        password=password,
    )


@pytest.mark.asyncio
async def test_login_returns_authentication_response() -> None:
    """
    It should authenticate the user and return an access token.
    """

    user = UserFactory.build(
        email="user@example.com",
    )

    service = MagicMock()

    service.authenticate = AsyncMock(
        return_value=user,
    )

    service.create_access_token.return_value = (
        "access-token",
        3600,
    )

    response = await login(
        form_data=build_form_data(),
        service=service,
    )

    assert isinstance(
        response,
        ApiResponse,
    )
    assert response.status_code == status.HTTP_200_OK

    response = json.loads(response.body)["data"]

    assert response["access_token"] == "access-token"
    assert response["expires_in"] == 3600

    service.authenticate.assert_awaited_once_with(
        email="user@example.com",
        password="password",
    )

    service.create_access_token.assert_called_once_with(
        user=user,
    )


@pytest.mark.asyncio
async def test_login_raises_unauthorized_for_invalid_credentials() -> None:
    """
    It should return HTTP 401 when authentication fails.
    """

    service = MagicMock()

    service.authenticate = AsyncMock(
        side_effect=ValueError(
            "Invalid email or password",
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await login(
            form_data=build_form_data(),
            service=service,
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid email or password"
    assert exc_info.value.headers == {
        "WWW-Authenticate": "Bearer",
    }

    service.authenticate.assert_awaited_once_with(
        email="user@example.com",
        password="password",
    )

    service.create_access_token.assert_not_called()


@pytest.mark.asyncio
async def test_login_raises_for_inactive_user() -> None:
    """
    It should return HTTP 403 when the user account is inactive.
    """

    service = MagicMock()

    service.authenticate = AsyncMock(
        side_effect=PermissionError(
            "User account is inactive",
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await login(
            form_data=build_form_data(),
            service=service,
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "User account is inactive"

    service.create_access_token.assert_not_called()


@pytest.mark.asyncio
async def test_login_returns_unauthorized_when_password_is_invalid() -> None:
    """
    It should return HTTP 401 for invalid credentials.
    """

    service = MagicMock()

    service.authenticate = AsyncMock(
        side_effect=ValueError(
            "Invalid email or password",
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await login(
            form_data=build_form_data(
                username="invalid@example.com",
                password="wrong-password",
            ),
            service=service,
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid email or password"

    service.create_access_token.assert_not_called()


@pytest.mark.asyncio
async def test_login_returns_internal_server_error_for_unexpected_error() -> None:
    """
    It should return HTTP 500 for unexpected authentication errors.
    """

    service = MagicMock()

    service.authenticate = AsyncMock(
        side_effect=RuntimeError(
            "database unavailable",
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        await login(
            form_data=build_form_data(),
            service=service,
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Authentication failed"

    service.create_access_token.assert_not_called()


@pytest.mark.asyncio
async def test_login_returns_internal_server_error_when_token_creation_fails() -> None:
    """
    It should return HTTP 500 when access token creation fails.
    """

    user = UserFactory.build(
        email="user@example.com",
    )

    service = MagicMock()

    service.authenticate = AsyncMock(
        return_value=user,
    )

    service.create_access_token.side_effect = RuntimeError(
        "token generation failed",
    )

    with pytest.raises(HTTPException) as exc_info:
        await login(
            form_data=build_form_data(),
            service=service,
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Authentication failed"

    service.authenticate.assert_awaited_once_with(
        email="user@example.com",
        password="password",
    )

    service.create_access_token.assert_called_once_with(
        user=user,
    )


@pytest.mark.asyncio
async def test_logout_returns_success_response() -> None:
    """
    It should return a successful logout response.
    """

    response = await logout()

    response = json.loads(response.body)

    assert response["message"] == "Logout successful."

    assert response["success"] is True


@pytest.mark.asyncio
async def test_access_token_returns_new_access_token() -> None:
    """
    It should exchange a valid refresh token for a new access token.
    """

    service = MagicMock()

    service.refresh_access_token = AsyncMock(
        return_value=(
            "new-access-token",
            3600,
        ),
    )

    request = RefreshTokenRequest(
        refresh_token="refresh-token",
    )

    response = await access_token(
        request=request,
        service=service,
    )

    response = json.loads(response.body)
    assert response["message"] == "Access token refreshed successfully."

    assert response["success"] is True

    assert response["data"]["access_token"] == "new-access-token"
    assert response["data"]["expires_in"] == 3600

    service.refresh_access_token.assert_awaited_once_with(
        refresh_token="refresh-token",
    )


@pytest.mark.asyncio
async def test_access_token_raises_unauthorized_for_invalid_refresh_token() -> None:
    """
    It should return HTTP 401 for an invalid refresh token.
    """

    service = MagicMock()

    service.refresh_access_token = AsyncMock(
        side_effect=ValueError(
            "Invalid refresh token",
        ),
    )

    request = RefreshTokenRequest(
        refresh_token="invalid-token",
    )

    with pytest.raises(HTTPException) as exc_info:
        await access_token(
            request=request,
            service=service,
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid refresh token"

    assert exc_info.value.headers == {
        "WWW-Authenticate": "Bearer",
    }

    service.refresh_access_token.assert_awaited_once_with(
        refresh_token="invalid-token",
    )


@pytest.mark.asyncio
async def test_access_token_raises_unauthorized_when_token_type_is_invalid() -> None:
    """
    It should return HTTP 401 when the refresh token has an invalid type.
    """

    service = MagicMock()

    service.refresh_access_token = AsyncMock(
        side_effect=ValueError(
            "Invalid token type",
        ),
    )

    request = RefreshTokenRequest(
        refresh_token="access-token",
    )

    with pytest.raises(HTTPException) as exc_info:
        await access_token(
            request=request,
            service=service,
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token type"

    assert exc_info.value.headers == {
        "WWW-Authenticate": "Bearer",
    }


@pytest.mark.asyncio
async def test_access_token_raises_unauthorized_when_user_is_unavailable() -> None:
    """
    It should return HTTP 401 when the refresh-token user is unavailable.
    """

    service = MagicMock()

    service.refresh_access_token = AsyncMock(
        side_effect=ValueError(
            "User is not available",
        ),
    )

    request = RefreshTokenRequest(
        refresh_token="refresh-token",
    )

    with pytest.raises(HTTPException) as exc_info:
        await access_token(
            request=request,
            service=service,
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "User is not available"

    assert exc_info.value.headers == {
        "WWW-Authenticate": "Bearer",
    }


@pytest.mark.asyncio
async def test_access_token_returns_internal_server_error_for_unexpected_error() -> None:
    """
    It should return HTTP 500 for unexpected refresh errors.
    """

    service = MagicMock()

    service.refresh_access_token = AsyncMock(
        side_effect=RuntimeError(
            "database unavailable",
        ),
    )

    request = RefreshTokenRequest(
        refresh_token="refresh-token",
    )

    with pytest.raises(HTTPException) as exc_info:
        await access_token(
            request=request,
            service=service,
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Unable to refresh access token"

    service.refresh_access_token.assert_awaited_once_with(
        refresh_token="refresh-token",
    )
