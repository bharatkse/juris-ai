"""
Unit tests for authentication dependencies.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from adapters.persistence.sqlalchemy.models.user import User
from api.dependencies.auth import get_current_user
from tests.factories.user import UserFactory


def build_user(
    *,
    is_active: bool = True,
) -> User:
    """
    Build a user for authentication dependency tests.
    """

    return UserFactory.build(
        is_active=is_active,
    )


@pytest.mark.asyncio
async def test_get_current_user_returns_active_user() -> None:
    """
    It should return the authenticated active user.
    """

    user = build_user()

    repository = MagicMock()

    repository.get = AsyncMock(
        return_value=user,
    )

    with (
        patch(
            "api.dependencies.auth.decode_token",
            return_value={
                "sub": user.id,
                "type": "access",
            },
        ) as mock_decode_token,
        patch(
            "api.dependencies.auth.is_token_type",
            return_value=True,
        ) as mock_is_token_type,
        patch(
            "api.dependencies.auth.get_subject",
            return_value=user.id,
        ) as mock_get_subject,
    ):
        result = await get_current_user(
            token="valid-access-token",
            user_repository=repository,
        )

    assert result is user

    mock_decode_token.assert_called_once_with(
        "valid-access-token",
    )

    mock_is_token_type.assert_called_once_with(
        {
            "sub": user.id,
            "type": "access",
        },
        "access",
    )

    mock_get_subject.assert_called_once_with(
        {
            "sub": user.id,
            "type": "access",
        },
    )

    repository.get.assert_awaited_once_with(
        user.id,
    )


@pytest.mark.asyncio
async def test_get_current_user_raises_unauthorized_for_invalid_token() -> None:
    """
    It should return HTTP 401 when the JWT cannot be decoded.
    """

    repository = MagicMock()

    repository.get = AsyncMock()

    from jose import JWTError

    with patch(
        "api.dependencies.auth.decode_token",
        side_effect=JWTError(),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token="invalid-token",
                user_repository=repository,
            )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Could not validate credentials"
    assert exc_info.value.headers == {
        "WWW-Authenticate": "Bearer",
    }

    repository.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_current_user_raises_unauthorized_for_non_access_token() -> None:
    """
    It should reject tokens that are not access tokens.
    """

    user = build_user()

    repository = MagicMock()
    repository.get = AsyncMock()

    payload = {
        "sub": user.id,
        "type": "refresh",
    }

    with (
        patch(
            "api.dependencies.auth.decode_token",
            return_value=payload,
        ),
        patch(
            "api.dependencies.auth.is_token_type",
            return_value=False,
        ) as mock_is_token_type,
        patch(
            "api.dependencies.auth.get_subject",
        ) as mock_get_subject,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token="refresh-token",
                user_repository=repository,
            )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Could not validate credentials"
    assert exc_info.value.headers == {
        "WWW-Authenticate": "Bearer",
    }

    mock_is_token_type.assert_called_once_with(
        payload,
        "access",
    )

    mock_get_subject.assert_not_called()
    repository.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_current_user_raises_unauthorized_when_subject_is_missing() -> None:
    """
    It should reject an access token without a subject.
    """

    repository = MagicMock()
    repository.get = AsyncMock()

    payload = {
        "type": "access",
    }

    with (
        patch(
            "api.dependencies.auth.decode_token",
            return_value=payload,
        ),
        patch(
            "api.dependencies.auth.is_token_type",
            return_value=True,
        ),
        patch(
            "api.dependencies.auth.get_subject",
            return_value=None,
        ) as mock_get_subject,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token="token-without-subject",
                user_repository=repository,
            )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Could not validate credentials"
    assert exc_info.value.headers == {
        "WWW-Authenticate": "Bearer",
    }

    mock_get_subject.assert_called_once_with(
        payload,
    )

    repository.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_current_user_raises_unauthorized_when_user_does_not_exist() -> None:
    """
    It should return HTTP 401 when the token subject
    does not correspond to an existing user.
    """

    user_id = "user_unknown"

    repository = MagicMock()

    repository.get = AsyncMock(
        return_value=None,
    )

    payload = {
        "sub": user_id,
        "type": "access",
    }

    with (
        patch(
            "api.dependencies.auth.decode_token",
            return_value=payload,
        ),
        patch(
            "api.dependencies.auth.is_token_type",
            return_value=True,
        ),
        patch(
            "api.dependencies.auth.get_subject",
            return_value=user_id,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token="valid-token",
                user_repository=repository,
            )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Could not validate credentials"
    assert exc_info.value.headers == {
        "WWW-Authenticate": "Bearer",
    }

    repository.get.assert_awaited_once_with(
        user_id,
    )


@pytest.mark.asyncio
async def test_get_current_user_raises_for_inactive_user() -> None:
    """
    It should return HTTP 403 when the authenticated user is inactive.
    """

    user = build_user(
        is_active=False,
    )

    repository = MagicMock()

    repository.get = AsyncMock(
        return_value=user,
    )

    payload = {
        "sub": user.id,
        "type": "access",
    }

    with (
        patch(
            "api.dependencies.auth.decode_token",
            return_value=payload,
        ),
        patch(
            "api.dependencies.auth.is_token_type",
            return_value=True,
        ),
        patch(
            "api.dependencies.auth.get_subject",
            return_value=user.id,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token="valid-token",
                user_repository=repository,
            )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "User account is inactive"

    repository.get.assert_awaited_once_with(
        user.id,
    )


@pytest.mark.asyncio
async def test_get_current_user_raises_unauthorized_when_token_subject_is_empty() -> None:
    """
    It should reject an access token with an empty subject.
    """

    repository = MagicMock()
    repository.get = AsyncMock()

    payload = {
        "sub": "",
        "type": "access",
    }

    with (
        patch(
            "api.dependencies.auth.decode_token",
            return_value=payload,
        ),
        patch(
            "api.dependencies.auth.is_token_type",
            return_value=True,
        ),
        patch(
            "api.dependencies.auth.get_subject",
            return_value=None,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(
                token="token-with-empty-subject",
                user_repository=repository,
            )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Could not validate credentials"

    repository.get.assert_not_awaited()
