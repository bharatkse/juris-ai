"""
Rate limiting / usage quota / upload limit exceptions.
"""

from core.constants import (
    ERROR_RATE_LIMIT_EXCEEDED,
    ERROR_TOKEN_QUOTA_EXCEEDED,
    HTTP_413_CONTENT_TOO_LARGE,
    HTTP_422_UNPROCESSABLE_ENTITY,
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


class TooManyUploadsError(DomainError):
    """
    Raised when a chat message attaches more files than allowed.
    """

    status_code = HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "TOO_MANY_UPLOADS"

    def __init__(
        self,
        *,
        limit: int,
        received: int,
    ) -> None:
        self.limit = limit
        self.received = received

        super().__init__(
            f"Too many files attached: {received}. At most {limit} files per message.",
        )


class UploadTooLargeError(DomainError):
    """
    Raised when an attached file is larger than allowed.
    """

    status_code = HTTP_413_CONTENT_TOO_LARGE
    error_code = "UPLOAD_TOO_LARGE"

    def __init__(
        self,
        *,
        filename: str,
        limit_bytes: int,
    ) -> None:
        self.filename = filename
        self.limit_bytes = limit_bytes

        super().__init__(
            f"File '{filename}' is too large: the limit is "
            f"{limit_bytes // (1024 * 1024)} MB per file.",
        )
