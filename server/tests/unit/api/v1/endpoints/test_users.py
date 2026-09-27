"""
Unit tests for user API endpoints.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

from api.utilities.api_response import ApiResponse
from api.v1.endpoints.users import (
    get_user_details,
    update_user_profile,
    user_registration,
)
from tests.builders.api.schemas import (
    build_create_user_request,
    build_update_user_request,
)
from tests.unit.factories.user import UserFactory


@pytest.mark.asyncio
@patch("api.v1.endpoints.users.UserResponse.model_validate")
async def test_create_user(
    mock_model_validate: MagicMock,
) -> None:
    """
    It should create a user.
    """

    user = UserFactory.build()

    request = build_create_user_request()

    response_model = MagicMock()

    mock_model_validate.return_value = response_model

    service = MagicMock()
    service.create = AsyncMock(
        return_value=user,
    )

    response = await user_registration(
        request=request,
        service=service,
    )

    assert isinstance(
        response,
        ApiResponse,
    )

    assert response.status_code == status.HTTP_201_CREATED

    service.create.assert_awaited_once_with(
        request=request,
    )

    mock_model_validate.assert_called_once_with(
        user,
        from_attributes=True,
    )


@pytest.mark.asyncio
@patch("api.v1.endpoints.users.UserResponse.model_validate")
async def test_get_user(
    mock_model_validate: MagicMock,
) -> None:
    """
    It should return a user.
    """

    user = UserFactory.build()

    response_model = MagicMock()

    mock_model_validate.return_value = response_model

    service = MagicMock()
    service.get_or_raise = AsyncMock(
        return_value=user,
    )

    response = await get_user_details(
        user_id=user.id,
        current_user=user,
        service=service,
    )

    assert isinstance(
        response,
        ApiResponse,
    )

    assert response.status_code == status.HTTP_200_OK

    service.get_or_raise.assert_awaited_once_with(
        user_id=user.id,
    )

    mock_model_validate.assert_called_once_with(
        user,
        from_attributes=True,
    )


@pytest.mark.asyncio
@patch("api.v1.endpoints.users.UserResponse.model_validate")
async def test_update_user(
    mock_model_validate: MagicMock,
) -> None:
    """
    It should update a user.
    """

    user = UserFactory.build()

    request = build_update_user_request()

    response_model = MagicMock()

    mock_model_validate.return_value = response_model

    service = MagicMock()
    service.update = AsyncMock(
        return_value=user,
    )

    response = await update_user_profile(
        user_id=user.id,
        request=request,
        current_user=user,
        service=service,
    )

    assert isinstance(
        response,
        ApiResponse,
    )

    assert response.status_code == status.HTTP_200_OK

    service.update.assert_awaited_once_with(
        user_id=user.id,
        request=request,
    )

    mock_model_validate.assert_called_once_with(
        user,
        from_attributes=True,
    )


@pytest.mark.asyncio
async def test_get_user_rejects_another_users_profile() -> None:
    """
    It should reject cross-user profile access.
    """

    current_user = UserFactory.build()
    other_user = UserFactory.build()

    with pytest.raises(HTTPException) as exc_info:
        await get_user_details(
            user_id=other_user.id,
            current_user=current_user,
            service=MagicMock(),
        )

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
