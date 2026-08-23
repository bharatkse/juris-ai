"""
Unit tests for UserService.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.exceptions.httpx import UserAlreadyExistsError, UserNotFoundError
from src.services.user import UserService
from tests.builders.schemas import build_create_user_request, build_update_user_request
from tests.factories.user import UserFactory


@pytest.mark.asyncio
async def test_create_creates_user(
    user_service: UserService,
    mock_user_repository: MagicMock,
    mock_password_service: MagicMock,
) -> None:
    """
    It should create a user.
    """

    request = build_create_user_request(
        email="john@example.com",
        password="secret123",
        confirm_password="secret123",
    )

    user = UserFactory.build(
        email="john@example.com",
    )

    mock_password_service.hash.return_value = "hashed-password"

    mock_user_repository.exists_by_email.return_value = False
    mock_user_repository.create.return_value = user

    user_service.commit = AsyncMock()
    user_service.rollback = AsyncMock()

    created = await user_service.create(
        request,
    )

    assert created is user

    mock_password_service.hash.assert_called_once_with(
        request.password,
    )

    mock_user_repository.exists_by_email.assert_awaited_once_with(
        "john@example.com",
    )

    mock_user_repository.create.assert_awaited_once()

    created_user = mock_user_repository.create.await_args.args[0]

    assert created_user.email == "john@example.com"
    assert created_user.password_hash == "hashed-password"

    user_service.commit.assert_awaited_once_with()
    user_service.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_normalizes_email(
    user_service: UserService,
    mock_user_repository: MagicMock,
    mock_password_service: MagicMock,
) -> None:
    """
    It should normalize the email address.
    """

    request = build_create_user_request(
        email="  Test@Example.COM ",
    )

    mock_password_service.hash.return_value = "hashed-password"

    mock_user_repository.exists_by_email.return_value = False
    mock_user_repository.create.side_effect = lambda user: user

    user_service.commit = AsyncMock()
    user_service.rollback = AsyncMock()

    user = await user_service.create(
        request,
    )

    assert user.email == "test@example.com"

    created_user = mock_user_repository.create.await_args.args[0]

    assert created_user.email == "test@example.com"

    user_service.commit.assert_awaited_once_with()
    user_service.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_hashes_password(
    user_service: UserService,
    mock_user_repository: MagicMock,
    mock_password_service: MagicMock,
) -> None:
    """
    It should hash the user's password.
    """

    request = build_create_user_request()

    mock_password_service.hash.return_value = "hashed-password"

    mock_user_repository.exists_by_email.return_value = False
    mock_user_repository.create.side_effect = lambda user: user

    user_service.commit = AsyncMock()

    await user_service.create(
        request,
    )

    mock_password_service.hash.assert_called_once_with(
        request.password,
    )

    created_user = mock_user_repository.create.await_args.args[0]

    assert created_user.password_hash == "hashed-password"


@pytest.mark.asyncio
async def test_create_raises_when_email_already_exists(
    user_service: UserService,
    mock_user_repository: MagicMock,
    mock_password_service: MagicMock,
) -> None:
    """
    It should fail when the email already exists.
    """

    mock_password_service.hash.return_value = "hashed-password"

    mock_user_repository.exists_by_email.return_value = True

    user_service.commit = AsyncMock()
    user_service.rollback = AsyncMock()

    with pytest.raises(
        UserAlreadyExistsError,
    ):
        await user_service.create(
            build_create_user_request(),
        )

    mock_user_repository.create.assert_not_called()

    user_service.commit.assert_not_awaited()
    user_service.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_rolls_back_when_repository_fails(
    user_service: UserService,
    mock_user_repository: MagicMock,
    mock_password_service: MagicMock,
) -> None:
    """
    It should roll back when user creation fails.
    """

    mock_password_service.hash.return_value = "hashed-password"

    mock_user_repository.exists_by_email.return_value = False
    mock_user_repository.create.side_effect = RuntimeError(
        "Database error",
    )

    user_service.commit = AsyncMock()
    user_service.rollback = AsyncMock()

    with pytest.raises(
        RuntimeError,
    ):
        await user_service.create(
            build_create_user_request(),
        )

    mock_user_repository.create.assert_awaited_once()

    user_service.commit.assert_not_awaited()
    user_service.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_create_rolls_back_when_commit_fails(
    user_service: UserService,
    mock_user_repository: MagicMock,
    mock_password_service: MagicMock,
) -> None:
    """
    It should roll back when committing fails.
    """

    mock_password_service.hash.return_value = "hashed-password"

    mock_user_repository.exists_by_email.return_value = False
    mock_user_repository.create.side_effect = lambda user: user

    user_service.commit = AsyncMock(
        side_effect=RuntimeError(
            "Commit failed",
        ),
    )

    user_service.rollback = AsyncMock()

    with pytest.raises(
        RuntimeError,
    ):
        await user_service.create(
            build_create_user_request(),
        )

    mock_user_repository.create.assert_awaited_once()

    user_service.commit.assert_awaited_once_with()
    user_service.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_get_returns_user(
    user_service: UserService,
    mock_user_repository: MagicMock,
) -> None:
    """
    It should return the requested user.
    """

    user = UserFactory.build()

    mock_user_repository.get.return_value = user

    found = await user_service.get(
        user.id,
    )

    assert found is user

    mock_user_repository.get.assert_awaited_once_with(
        user.id,
    )


@pytest.mark.asyncio
async def test_update_updates_user(
    user_service: UserService,
    mock_user_repository: MagicMock,
) -> None:
    """
    It should update the user's profile.
    """

    user = UserFactory.build()

    request = build_update_user_request(
        first_name="Jane",
    )

    mock_user_repository.get.return_value = user
    mock_user_repository.update.return_value = user

    user_service.commit = AsyncMock()
    user_service.rollback = AsyncMock()

    updated = await user_service.update(
        user.id,
        request,
    )

    assert updated is user
    assert updated.first_name == "Jane"

    mock_user_repository.update.assert_awaited_once_with(
        user,
    )

    user_service.commit.assert_awaited_once_with()
    user_service.rollback.assert_not_awaited()


# @pytest.mark.asyncio
# async def test_update_normalizes_email(
#     user_service: UserService,
#     mock_user_repository: MagicMock,
# ) -> None:
#     """
#     It should normalize the updated email.
#     """

#     user = UserFactory.build(
#         email="old@example.com",
#     )

#     request = build_update_user_request(
#         email="  New@Example.COM ",
#     )

#     mock_user_repository.get.return_value = user
#     mock_user_repository.exists_by_email.return_value = False

#     user_service.commit = AsyncMock()

#     await user_service.update(
#         user.id,
#         request,
#     )

#     assert user.email == "new@example.com"

#     mock_user_repository.exists_by_email.assert_awaited_once_with(
#         "new@example.com",
#     )


# @pytest.mark.asyncio
# async def test_update_does_not_check_duplicate_email_when_unchanged(
#     user_service: UserService,
#     mock_user_repository: MagicMock,
# ) -> None:
#     """
#     It should not check for duplicate email when unchanged.
#     """

#     user = UserFactory.build(
#         email="john@example.com",
#     )

#     request = build_update_user_request(
#         email="john@example.com",
#     )

#     mock_user_repository.get.return_value = user

#     user_service.commit = AsyncMock()

#     await user_service.update(
#         user.id,
#         request,
#     )

#     mock_user_repository.exists_by_email.assert_not_called()


@pytest.mark.asyncio
async def test_update_raises_when_user_does_not_exist(
    user_service: UserService,
    mock_user_repository: MagicMock,
) -> None:
    """
    It should fail when the user does not exist.
    """

    mock_user_repository.get.return_value = None

    with pytest.raises(
        UserNotFoundError,
    ):
        await user_service.update(
            UserFactory.build().id,
            build_update_user_request(),
        )

    mock_user_repository.update.assert_not_called()


# @pytest.mark.asyncio
# async def test_update_raises_when_email_already_exists(
#     user_service: UserService,
#     mock_user_repository: MagicMock,
# ) -> None:
#     """
#     It should fail when the new email already exists.
#     """

#     user = UserFactory.build(
#         email="old@example.com",
#     )

#     request = build_update_user_request(
#         email="new@example.com",
#     )

#     mock_user_repository.get.return_value = user
#     mock_user_repository.exists_by_email.return_value = True

#     with pytest.raises(
#         UserAlreadyExistsError,
#     ):
#         await user_service.update(
#             user.id,
#             request,
#         )

#     mock_user_repository.update.assert_not_called()


@pytest.mark.asyncio
async def test_update_rolls_back_when_repository_fails(
    user_service: UserService,
    mock_user_repository: MagicMock,
) -> None:
    """
    It should roll back when updating fails.
    """

    user = UserFactory.build()

    mock_user_repository.get.return_value = user
    mock_user_repository.update.side_effect = RuntimeError(
        "Database error",
    )

    user_service.commit = AsyncMock()
    user_service.rollback = AsyncMock()

    with pytest.raises(
        RuntimeError,
    ):
        await user_service.update(
            user.id,
            build_update_user_request(),
        )

    mock_user_repository.update.assert_awaited_once_with(
        user,
    )

    user_service.commit.assert_not_awaited()
    user_service.rollback.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_update_rolls_back_when_commit_fails(
    user_service: UserService,
    mock_user_repository: MagicMock,
) -> None:
    """
    It should roll back when committing an update fails.
    """

    user = UserFactory.build()

    mock_user_repository.get.return_value = user
    mock_user_repository.update.return_value = None

    user_service.commit = AsyncMock(
        side_effect=RuntimeError(
            "Commit failed",
        ),
    )

    user_service.rollback = AsyncMock()

    with pytest.raises(
        RuntimeError,
    ):
        await user_service.update(
            user.id,
            build_update_user_request(),
        )

    mock_user_repository.update.assert_awaited_once_with(
        user,
    )

    user_service.commit.assert_awaited_once_with()
    user_service.rollback.assert_awaited_once_with()


def test_create_user_request_rejects_mismatched_passwords() -> None:
    with pytest.raises(ValueError):
        build_create_user_request(
            password="Password@123",
            confirm_password="Another@123",
        )
