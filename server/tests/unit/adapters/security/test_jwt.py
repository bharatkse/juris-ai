"""
Unit tests for JWT token utilities.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from jose import JWTError, jwt

from adapters.security.jwt import (
    create_access_token,
    decode_token,
    get_subject,
    is_token_type,
)


def _build_mock_settings() -> MagicMock:
    """Helper to construct mock settings conforming to the modular structure."""
    settings = MagicMock()
    settings.security.access_token_expire_minutes = 60
    settings.security.jwt_secret_key = "test-secret"
    settings.security.JWT_ALGORITHM = "HS256"
    return settings


def test_create_access_token_returns_token_and_expiration() -> None:
    """
    It should create an access token and return its expiration duration.
    """

    user = MagicMock()
    user.id = "user_123"
    user.email = "user@example.com"

    settings = _build_mock_settings()

    with patch(
        "adapters.security.jwt.get_settings",
        return_value=settings,
    ):
        token, expires_in = create_access_token(
            user,
        )

    assert isinstance(token, str)
    assert token
    assert expires_in == 3600


def test_create_access_token_contains_expected_claims() -> None:
    """
    It should include the expected JWT claims.
    """

    user = MagicMock()
    user.id = "user_123"
    user.email = "user@example.com"

    settings = _build_mock_settings()

    with patch(
        "adapters.security.jwt.get_settings",
        return_value=settings,
    ):
        token, expires_in = create_access_token(
            user,
        )

        payload = jwt.decode(
            token,
            settings.security.jwt_secret_key,
            algorithms=[settings.security.JWT_ALGORITHM],
        )

    assert payload["sub"] == "user_123"
    assert payload["email"] == "user@example.com"
    assert payload["type"] == "access"
    assert "iat" in payload
    assert "exp" in payload
    assert expires_in == 3600


def test_create_access_token_sets_expected_expiration() -> None:
    """
    It should set the expiration according to the configured lifetime.
    """

    user = MagicMock()
    user.id = "user_123"
    user.email = "user@example.com"

    settings = _build_mock_settings()
    settings.security.access_token_expire_minutes = 30

    with patch(
        "adapters.security.jwt.get_settings",
        return_value=settings,
    ):
        token, expires_in = create_access_token(
            user,
        )

        payload = jwt.decode(
            token,
            settings.security.jwt_secret_key,
            algorithms=[settings.security.JWT_ALGORITHM],
        )

    issued_at = datetime.fromtimestamp(
        payload["iat"],
        tz=UTC,
    )

    expiration = datetime.fromtimestamp(
        payload["exp"],
        tz=UTC,
    )

    assert expires_in == 1800
    assert expiration - issued_at == timedelta(
        seconds=1800,
    )


def test_create_access_token_propagates_encoding_error() -> None:
    """
    It should propagate an unexpected token encoding error.
    """

    user = MagicMock()
    user.id = "user_123"
    user.email = "user@example.com"

    settings = _build_mock_settings()

    with (
        patch(
            "adapters.security.jwt.get_settings",
            return_value=settings,
        ),
        patch(
            "adapters.security.jwt.jwt.encode",
            side_effect=RuntimeError(
                "encoding failed",
            ),
        ),
    ):
        with pytest.raises(
            RuntimeError,
            match="encoding failed",
        ):
            create_access_token(
                user,
            )


def test_decode_token_returns_payload() -> None:
    """
    It should decode a valid JWT and return its payload.
    """

    settings = _build_mock_settings()

    payload = {
        "sub": "user_123",
        "email": "user@example.com",
        "type": "access",
    }

    token = jwt.encode(
        payload,
        settings.security.jwt_secret_key,
        algorithm=settings.security.JWT_ALGORITHM,
    )

    with patch(
        "adapters.security.jwt.get_settings",
        return_value=settings,
    ):
        result = decode_token(
            token,
        )

    assert result["sub"] == "user_123"
    assert result["email"] == "user@example.com"
    assert result["type"] == "access"


def test_decode_token_raises_for_invalid_token() -> None:
    """
    It should raise JWTError for an invalid token.
    """

    settings = _build_mock_settings()

    with patch(
        "adapters.security.jwt.get_settings",
        return_value=settings,
    ):
        with pytest.raises(JWTError):
            decode_token(
                "invalid-token",
            )


def test_decode_token_raises_for_token_signed_with_wrong_secret() -> None:
    """
    It should reject a token signed with another secret.
    """

    settings = _build_mock_settings()

    token = jwt.encode(
        {
            "sub": "user_123",
            "type": "access",
        },
        "different-secret",
        algorithm="HS256",
    )

    with patch(
        "adapters.security.jwt.get_settings",
        return_value=settings,
    ):
        with pytest.raises(JWTError):
            decode_token(
                token,
            )


def test_decode_token_raises_for_expired_token() -> None:
    """
    It should reject an expired JWT.
    """

    settings = _build_mock_settings()

    token = jwt.encode(
        {
            "sub": "user_123",
            "type": "access",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        settings.security.jwt_secret_key,
        algorithm=settings.security.JWT_ALGORITHM,
    )

    with patch(
        "adapters.security.jwt.get_settings",
        return_value=settings,
    ):
        with pytest.raises(JWTError):
            decode_token(
                token,
            )


def test_decode_token_propagates_unexpected_error() -> None:
    """
    It should propagate unexpected JWT infrastructure errors.
    """

    settings = _build_mock_settings()

    with (
        patch(
            "adapters.security.jwt.get_settings",
            return_value=settings,
        ),
        patch(
            "adapters.security.jwt.jwt.decode",
            side_effect=RuntimeError(
                "unexpected JWT failure",
            ),
        ),
    ):
        with pytest.raises(
            RuntimeError,
            match="unexpected JWT failure",
        ):
            decode_token(
                "token",
            )


def test_is_token_type_returns_true_for_matching_type() -> None:
    """
    It should return True when the token type matches.
    """

    payload = {
        "type": "access",
    }

    assert (
        is_token_type(
            payload,
            "access",
        )
        is True
    )


def test_is_token_type_returns_false_for_different_type() -> None:
    """
    It should return False when the token type does not match.
    """

    payload = {
        "type": "access",
    }

    assert (
        is_token_type(
            payload,
            "refresh",
        )
        is False
    )


def test_is_token_type_returns_false_when_type_is_missing() -> None:
    """
    It should return False when the token type is missing.
    """

    payload = {
        "sub": "user_123",
    }

    assert (
        is_token_type(
            payload,
            "access",
        )
        is False
    )


def test_is_token_type_returns_false_for_none_type() -> None:
    """
    It should return False when the token type is None.
    """

    payload = {
        "type": None,
    }

    assert (
        is_token_type(
            payload,
            "access",
        )
        is False
    )


def test_get_subject_returns_subject() -> None:
    """
    It should return the token subject.
    """

    payload = {
        "sub": "user_123",
    }

    assert (
        get_subject(
            payload,
        )
        == "user_123"
    )


def test_get_subject_converts_subject_to_string() -> None:
    """
    It should convert a non-string subject to a string.
    """

    payload = {
        "sub": 12345,
    }

    assert (
        get_subject(
            payload,
        )
        == "12345"
    )


def test_get_subject_returns_none_when_subject_is_missing() -> None:
    """
    It should return None when the subject is missing.
    """

    payload = {
        "type": "access",
    }

    assert (
        get_subject(
            payload,
        )
        is None
    )


def test_get_subject_returns_none_when_subject_is_empty() -> None:
    """
    It should return None when the subject is empty.
    """

    payload = {
        "sub": "",
    }

    assert (
        get_subject(
            payload,
        )
        is None
    )


def test_get_subject_returns_none_when_subject_is_none() -> None:
    """
    It should return None when the subject is None.
    """

    payload = {
        "sub": None,
    }

    assert (
        get_subject(
            payload,
        )
        is None
    )
