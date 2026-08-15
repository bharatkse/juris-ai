from unittest.mock import MagicMock

from groq import AuthenticationError, RateLimitError


def build_authentication_error() -> AuthenticationError:
    return AuthenticationError(
        "Authentication failed",
        response=MagicMock(),
        body={},
    )


def build_rate_limit_error() -> RateLimitError:
    return RateLimitError(
        "Rate limit exceeded",
        response=MagicMock(),
        body={},
    )
