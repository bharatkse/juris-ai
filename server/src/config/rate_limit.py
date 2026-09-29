from __future__ import annotations

from pydantic import field_validator

from config.base import BaseAppSettings


class RateLimitSettings(BaseAppSettings):
    """
    Per-user request-rate and token-quota configuration.

    The defaults are placeholders, not derived from real traffic/cost
    data -- tune via env vars once real usage numbers exist.
    """

    RATE_LIMIT_ENABLED: bool = True

    # (a) burst/rate limit: max requests per rolling-minute window.
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 20

    # (b) cost control: max total (input + output) tokens per user per
    # calendar day.
    RATE_LIMIT_DAILY_TOKEN_QUOTA: int = 200_000

    # (b2) cost control per request: max total tokens one chat request's
    # LLM calls may use. Checked before each call (core/usage.py), so a
    # call that would cross it is never made; the request fails with 413
    # REQUEST_TOKEN_QUOTA_EXCEEDED and the tokens already used still
    # count toward the daily quota. Not applied to a turn resumed after
    # an approval (that turn was admitted before the approval).
    RATE_LIMIT_REQUEST_TOKEN_QUOTA: int = 100_000

    # (c) chat attachments (api/helpers/files.py): checked before a file
    # is read into memory, along with its type (only the types the parser
    # reads, core.constants.SUPPORTED_UPLOAD_CONTENT_TYPES; not a setting,
    # since another type couldn't be used). Each file's parsed text is also capped at
    # 20,000 characters before it reaches the model
    # (agentic/execution/attachments.py); that bounds the prompt, not
    # memory, parsing time or the number of files.
    UPLOAD_MAX_FILES: int = 5
    UPLOAD_MAX_FILE_BYTES: int = 10 * 1024 * 1024

    @field_validator(
        "RATE_LIMIT_REQUESTS_PER_MINUTE",
        "RATE_LIMIT_DAILY_TOKEN_QUOTA",
        "RATE_LIMIT_REQUEST_TOKEN_QUOTA",
        "UPLOAD_MAX_FILES",
        "UPLOAD_MAX_FILE_BYTES",
    )
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Rate-limit values must be greater than zero.")
        return value
