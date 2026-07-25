"""
Unit tests for user API endpoints.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status

from src.api.v1.endpoints.users import create_user, get_user, update_user
from src.core.response import ApiResponse
from tests.builders.schemas import build_create_user_request, build_update_user_request
from tests.factories.user import UserFactory


@pytest.mark.asyncio
@patch("src.api.v1.endpoints.users.UserResponse.model_validate")
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

    response = await create_user(
        request=request,
        service=service,
    )

    assert isinstance(
        response,
        ApiResponse,
    )

    assert response.status_code == status.HTTP_201_CREATED

    service.create.assert_awaited_once_with(
        request,
    )

    mock_model_validate.assert_called_once_with(
        user,
        from_attributes=True,
    )


@pytest.mark.asyncio
@patch("src.api.v1.endpoints.users.UserResponse.model_validate")
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
    service.get = AsyncMock(
        return_value=user,
    )

    response = await get_user(
        user_id=user.id,
        service=service,
    )

    assert isinstance(
        response,
        ApiResponse,
    )

    assert response.status_code == status.HTTP_200_OK

    service.get.assert_awaited_once_with(
        user.id,
    )

    mock_model_validate.assert_called_once_with(
        user,
        from_attributes=True,
    )


@pytest.mark.asyncio
@patch("src.api.v1.endpoints.users.UserResponse.model_validate")
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

    response = await update_user(
        user_id=user.id,
        request=request,
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
