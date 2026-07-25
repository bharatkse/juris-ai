"""
Unit tests for PasswordService.
"""

from __future__ import annotations

import pytest

from src.security.password import PasswordService


def test_hash_returns_password_hash() -> None:
    """
    It should hash a plaintext password.
    """

    password = "Password@123"

    password_hash = PasswordService.hash(
        password,
    )

    assert password_hash != password
    assert isinstance(
        password_hash,
        str,
    )


def test_hash_raises_when_password_is_empty() -> None:
    """
    It should reject an empty password.
    """

    with pytest.raises(
        ValueError,
        match="Password cannot be empty.",
    ):
        PasswordService.hash(
            "",
        )


def test_hash_raises_when_password_contains_only_whitespace() -> None:
    """
    It should reject a whitespace-only password.
    """

    with pytest.raises(
        ValueError,
        match="Password cannot be empty.",
    ):
        PasswordService.hash(
            "   ",
        )


def test_verify_returns_true_for_matching_password() -> None:
    """
    It should verify a matching password.
    """

    password = "Password@123"

    password_hash = PasswordService.hash(
        password,
    )

    assert PasswordService.verify(
        password,
        password_hash,
    )


def test_verify_returns_false_for_invalid_password() -> None:
    """
    It should reject an invalid password.
    """

    password_hash = PasswordService.hash(
        "Password@123",
    )

    assert not PasswordService.verify(
        "WrongPassword",
        password_hash,
    )


def test_verify_returns_false_for_invalid_hash() -> None:
    """
    It should return False for an invalid password hash.
    """

    assert not PasswordService.verify(
        "Password@123",
        "invalid-hash",
    )
