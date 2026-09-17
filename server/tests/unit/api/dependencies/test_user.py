"""
Unit tests for user dependencies.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from adapters.security.password import PasswordService
from api.dependencies.user import (
    get_password_service,
    get_user_repository,
    get_user_service,
)


def test_get_password_service() -> None:
    """
    It should create a password service.
    """

    service = get_password_service()

    assert isinstance(
        service,
        PasswordService,
    )


@patch("api.dependencies.user.UserRepository")
def test_get_user_repository(
    mock_user_repository: MagicMock,
) -> None:
    """
    It should create a user repository.
    """

    session = MagicMock()
    repository = MagicMock()

    mock_user_repository.return_value = repository

    result = get_user_repository(
        session=session,
    )

    assert result is repository

    mock_user_repository.assert_called_once_with(
        session=session,
    )


@patch("api.dependencies.user.UserService")
def test_get_user_service(
    mock_user_service: MagicMock,
) -> None:
    """
    It should create a user service.
    """

    session = MagicMock()
    repository = MagicMock()
    password_service = MagicMock()
    service = MagicMock()

    mock_user_service.return_value = service

    result = get_user_service(
        session=session,
        repository=repository,
        password_service=password_service,
    )

    assert result is service

    mock_user_service.assert_called_once_with(
        session=session,
        repository=repository,
        password_service=password_service,
    )
