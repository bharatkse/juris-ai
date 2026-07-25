"""
Unit tests for the User ORM model.
"""

from __future__ import annotations

from tests.factories.user import UserFactory


def test_full_name_returns_first_and_last_name() -> None:
    """
    It should concatenate the first and last name.
    """

    user = UserFactory(
        first_name="Bharat",
        last_name="Kumar",
    )

    assert user.full_name == "Bharat Kumar"


def test_full_name_returns_first_name_when_last_name_is_missing() -> None:
    """
    It should return only the first name.
    """

    user = UserFactory(
        first_name="Bharat",
        last_name=None,
    )

    assert user.full_name == "Bharat"


def test_full_name_returns_last_name_when_first_name_is_missing() -> None:
    """
    It should return only the last name.
    """

    user = UserFactory(
        first_name=None,
        last_name="Kumar",
    )

    assert user.full_name == "Kumar"


def test_full_name_returns_empty_string_when_names_are_missing() -> None:
    """
    It should return an empty string.
    """

    user = UserFactory(
        first_name=None,
        last_name=None,
    )

    assert user.full_name == ""


def test_user_is_active_by_default() -> None:
    """
    It should create an active user by default.
    """

    user = UserFactory()

    assert user.is_active is True


def test_user_can_be_created_as_inactive() -> None:
    """
    It should support the inactive trait.
    """

    user = UserFactory(
        inactive=True,
    )

    assert user.is_active is False


def test_repr_contains_identifier() -> None:
    """
    It should include the identifier.
    """

    user = UserFactory()

    assert user.id in repr(user)


def test_repr_contains_email() -> None:
    """
    It should include the email address.
    """

    user = UserFactory()

    assert user.email in repr(user)
