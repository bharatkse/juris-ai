"""
Rate limiting / usage quota exceptions.
"""

from core.constants import (
    ERROR_RATE_LIMIT_EXCEEDED,
    ERROR_TOKEN_QUOTA_EXCEEDED,
    HTTP_429_TOO_MANY_REQUESTS,
)
from core.exceptions.base import DomainError


class RateLimitExceededError(DomainError):
    """
    Raised when a user exceeds the per-minute request-rate limit.
    """

    status_code = HTTP_429_TOO_MANY_REQUESTS
    error_code = ERROR_RATE_LIMIT_EXCEEDED

    def __init__(
        self,
        *,
        limit: int,
        retry_after_seconds: int,
    ) -> None:
        self.limit = limit
        self.retry_after_seconds = retry_after_seconds

        super().__init__(
            f"Rate limit exceeded: max {limit} requests per minute. "
            f"Retry after {retry_after_seconds} second(s).",
        )


class TokenQuotaExceededError(DomainError):
    """
    Raised when a user has exhausted their daily token quota.
    """

    status_code = HTTP_429_TOO_MANY_REQUESTS
    error_code = ERROR_TOKEN_QUOTA_EXCEEDED

    def __init__(
        self,
        *,
        quota: int,
        used: int,
    ) -> None:
        self.quota = quota
        self.used = used

        super().__init__(
            f"Daily token quota exceeded: used {used}/{quota} tokens today. "
            "Quota resets at midnight UTC.",
        )
