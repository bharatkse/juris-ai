"""
Unit tests for user schemas.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from src.api.schemas.user import CreateUserRequest, UpdateUserRequest, UserResponse
from src.core.enums import GenderEnum
from tests.builders.schemas import build_create_user_request, build_update_user_request
from tests.factories.user import UserFactory


def test_create_user_request_accepts_valid_request() -> None:
    """
    It should accept a valid request.
    """

    request = build_create_user_request()

    assert request.email == "john@example.com"
    assert request.password == "Password@123"
    assert request.confirm_password == "Password@123"


def test_create_user_request_raises_when_passwords_do_not_match() -> None:
    """
    It should reject mismatched passwords.
    """

    with pytest.raises(
        ValidationError,
        match="Passwords do not match.",
    ):
        build_create_user_request(
            password="Password@123",
            confirm_password="Password@456",
        )


def test_create_user_request_rejects_invalid_email() -> None:
    """
    It should reject an invalid email.
    """

    with pytest.raises(
        ValidationError,
    ):
        build_create_user_request(
            email="invalid-email",
        )


def test_create_user_request_rejects_extra_fields() -> None:
    """
    It should reject unexpected fields.
    """

    with pytest.raises(
        ValidationError,
    ):
        CreateUserRequest(
            email="john@example.com",
            password="Password@123",
            confirm_password="Password@123",
            unknown="value",
        )


def test_create_user_request_requires_email() -> None:
    """
    It should require an email address.
    """

    with pytest.raises(
        ValidationError,
    ):
        CreateUserRequest(
            password="Password@123",
            confirm_password="Password@123",
        )


def test_create_user_request_requires_password() -> None:
    """
    It should require a password.
    """

    with pytest.raises(
        ValidationError,
    ):
        CreateUserRequest(
            email="john@example.com",
            confirm_password="Password@123",
        )


def test_create_user_request_requires_confirm_password() -> None:
    """
    It should require a confirmation password.
    """

    with pytest.raises(
        ValidationError,
    ):
        CreateUserRequest(
            email="john@example.com",
            password="Password@123",
        )


def test_update_user_request_accepts_partial_update() -> None:
    """
    It should accept a partial update request.
    """

    request = build_update_user_request(
        first_name="Jane",
    )

    assert request.first_name == "Jane"
    assert request.last_name is None
    assert request.gender is None
    assert request.phone_number is None
    assert request.date_of_birth is None


def test_update_user_request_accepts_all_fields() -> None:
    """
    It should accept all supported fields.
    """

    request = build_update_user_request(
        first_name="John",
        last_name="Doe",
        gender=GenderEnum.MALE,
        phone_number="9876543210",
        date_of_birth=date(
            1995,
            1,
            1,
        ),
    )

    assert request.first_name == "John"
    assert request.last_name == "Doe"
    assert request.gender == GenderEnum.MALE
    assert request.phone_number == "9876543210"
    assert request.date_of_birth == date(
        1995,
        1,
        1,
    )


def test_update_user_request_rejects_extra_fields() -> None:
    """
    It should reject unexpected fields.
    """

    with pytest.raises(
        ValidationError,
    ):
        UpdateUserRequest(
            first_name="John",
            unknown="value",
        )


def test_update_user_request_rejects_short_first_name() -> None:
    """
    It should reject a first name that is too short.
    """

    with pytest.raises(
        ValidationError,
    ):
        build_update_user_request(
            first_name="J",
        )


def test_update_user_request_rejects_short_last_name() -> None:
    """
    It should reject a last name that is too short.
    """

    with pytest.raises(
        ValidationError,
    ):
        build_update_user_request(
            last_name="D",
        )


def test_update_user_request_rejects_short_phone_number() -> None:
    """
    It should reject a phone number that is too short.
    """

    with pytest.raises(
        ValidationError,
    ):
        build_update_user_request(
            phone_number="123",
        )


def test_user_response_can_be_created_from_user() -> None:
    """
    It should create a response from a user entity.
    """

    user = UserFactory.build()

    response = UserResponse.model_validate(
        user,
    )

    assert response.id == user.id
    assert response.email == user.email
    assert response.first_name == user.first_name
    assert response.last_name == user.last_name
    assert response.gender == user.gender
    assert response.phone_number == user.phone_number
    assert response.date_of_birth == user.date_of_birth
    assert response.created_at == user.created_at
    assert response.updated_at == user.updated_at


def test_user_response_model_dump() -> None:
    """
    It should serialize the response.
    """

    user = UserFactory.build()

    response = UserResponse.model_validate(
        user,
    )

    data = response.model_dump()

    assert data["id"] == user.id
    assert data["email"] == user.email
    assert data["first_name"] == user.first_name
    assert data["last_name"] == user.last_name
    assert data["gender"] == user.gender
    assert data["phone_number"] == user.phone_number
    assert data["date_of_birth"] == user.date_of_birth


def test_user_response_rejects_extra_fields() -> None:
    """
    It should reject unexpected fields.
    """

    with pytest.raises(
        ValidationError,
    ):
        UserResponse(
            id="user_123",
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            gender=GenderEnum.MALE,
            phone_number="9876543210",
            date_of_birth=date(
                1995,
                1,
                1,
            ),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            unknown="value",
        )
