"""
Unit tests for UserRepository.
"""

from __future__ import annotations

import pytest

from tests.factories.user import UserFactory
from tests.helpers.identifiers import unknown_user_id


@pytest.mark.asyncio
async def test_create_persists_user(
    user_repository,
):
    """
    It should persist a user.
    """

    user = UserFactory.build()

    created = await user_repository.create(
        user,
    )

    assert created is user


@pytest.mark.asyncio
async def test_create_generates_identifier(
    user_repository,
):
    """
    It should generate an identifier.
    """

    user = UserFactory.build()

    created = await user_repository.create(
        user,
    )

    assert created.id is not None


@pytest.mark.asyncio
async def test_create_sets_timestamps(
    user_repository,
):
    """
    It should populate timestamps.
    """

    user = UserFactory.build()

    created = await user_repository.create(
        user,
    )

    assert created.created_at is not None
    assert created.updated_at is not None


@pytest.mark.asyncio
async def test_get_returns_existing_user(
    user_repository,
):
    """
    It should retrieve an existing user.
    """

    user = await user_repository.create(
        UserFactory.build(),
    )

    found = await user_repository.get(
        user.id,
    )

    assert found == user


@pytest.mark.asyncio
async def test_get_returns_none_when_user_does_not_exist(
    user_repository,
):
    """
    It should return None for an unknown identifier.
    """

    found = await user_repository.get(
        unknown_user_id(),
    )

    assert found is None


@pytest.mark.asyncio
async def test_get_by_email_returns_user(
    user_repository,
):
    """
    It should retrieve a user by email.
    """

    user = await user_repository.create(
        UserFactory.build(),
    )

    found = await user_repository.get_by_email(
        user.email,
    )

    assert found == user


@pytest.mark.asyncio
async def test_get_by_email_returns_none_when_email_does_not_exist(
    user_repository,
):
    """
    It should return None for an unknown email.
    """

    found = await user_repository.get_by_email(
        "missing@example.com",
    )

    assert found is None


@pytest.mark.asyncio
async def test_exists_by_email_returns_true(
    user_repository,
):
    """
    It should return True when the email exists.
    """

    user = await user_repository.create(
        UserFactory.build(),
    )

    exists = await user_repository.exists_by_email(
        user.email,
    )

    assert exists is True


@pytest.mark.asyncio
async def test_exists_by_email_returns_false(
    user_repository,
):
    """
    It should return False when the email does not exist.
    """

    exists = await user_repository.exists_by_email(
        "missing@example.com",
    )

    assert exists is False


@pytest.mark.asyncio
async def test_update_persists_changes(
    user_repository,
):
    """
    It should persist updates.
    """

    user = await user_repository.create(
        UserFactory.build(),
    )

    user.first_name = "Updated"

    updated = await user_repository.update(
        user,
    )

    assert updated.first_name == "Updated"


@pytest.mark.asyncio
async def test_update_returns_same_instance(
    user_repository,
):
    """
    It should return the updated user.
    """

    user = await user_repository.create(
        UserFactory.build(),
    )

    updated = await user_repository.update(
        user,
    )

    assert updated is user
