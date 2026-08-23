"""
JWT token utilities.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from src.core.config import get_settings
from src.db.models.user import User

logger = logging.getLogger(__name__)


def create_access_token(
    user: User,
) -> tuple[str, int]:
    """
    Create an access token for a user.
    """

    settings = get_settings()

    expires_in = settings.access_token_expire_minutes * 60

    now = datetime.now(UTC)
    expires_at = now + timedelta(
        seconds=expires_in,
    )

    payload = {
        "sub": str(user.id),
        "email": user.email,
        "type": "access",
        "iat": now,
        "exp": expires_at,
    }

    try:
        token = jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
    except Exception:
        logger.exception(
            "Failed to create access token user_id=%s",
            user.id,
        )
        raise

    logger.debug(
        "Access token created user_id=%s expires_in=%s",
        user.id,
        expires_in,
    )

    return token, expires_in


def decode_token(
    token: str,
) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Raises:
        JWTError: If the token is invalid, expired, malformed,
            or cannot be decoded.
        RuntimeError: If an unexpected JWT infrastructure error occurs.
    """

    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError:
        logger.warning(
            "JWT validation failed",
        )
        raise
    except Exception:
        logger.exception(
            "Unexpected error while decoding JWT",
        )
        raise

    logger.debug(
        "JWT decoded successfully",
    )

    return payload


def is_token_type(
    payload: dict[str, Any],
    token_type: str,
) -> bool:
    """
    Check whether a JWT has the expected token type.
    """

    actual_type = payload.get("type")

    if actual_type != token_type:
        logger.warning(
            "Invalid JWT token type expected=%s actual=%s",
            token_type,
            actual_type,
        )

        return False

    return True


def get_subject(
    payload: dict[str, Any],
) -> str | None:
    """
    Return the token subject.
    """

    subject = payload.get("sub")

    if not subject:
        logger.warning(
            "JWT subject is missing",
        )

        return None

    return str(subject)
