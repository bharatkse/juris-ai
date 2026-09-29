"""
Rate limiting / usage quota / upload limit exceptions.
"""

from core.constants import (
    ERROR_RATE_LIMIT_EXCEEDED,
    ERROR_REQUEST_TOKEN_QUOTA_EXCEEDED,
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


class RequestTokenQuotaExceededError(DomainError):
    """
    Raised when one request would use more tokens than a single request
    may (RATE_LIMIT_REQUEST_TOKEN_QUOTA).

    Raised before the LLM call that would cross the quota, never after
    it (core.usage). prompt_tokens/completion_tokens are what the
    request's earlier calls had already used, so that usage can still
    be recorded against the daily quota.
    """

    status_code = HTTP_413_CONTENT_TOO_LARGE
    error_code = ERROR_REQUEST_TOKEN_QUOTA_EXCEEDED

    def __init__(
        self,
        *,
        quota: int,
        used: int,
        requested: int,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        self.quota = quota
        self.used = used
        self.requested = requested
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens

        super().__init__(
            f"This request needs more than the {quota} tokens one request may use "
            f"({used} used, about {requested} more needed). "
            "Try a shorter message or fewer attachments.",
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


class UnsupportedUploadTypeError(DomainError):
    """
    Raised when an attached file isn't of a type the parser can read.
    """

    status_code = HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "UPLOAD_UNSUPPORTED_TYPE"

    def __init__(
        self,
        *,
        filename: str,
        content_type: str,
        supported: frozenset[str],
    ) -> None:
        self.filename = filename
        self.content_type = content_type
        self.supported = supported

        super().__init__(
            f"File '{filename}' has an unsupported type '{content_type}'. "
            f"Supported types: {', '.join(sorted(supported))}.",
        )
