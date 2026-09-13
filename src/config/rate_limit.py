from __future__ import annotations

from pydantic import field_validator

from config.base import BaseAppSettings


class RateLimitSettings(BaseAppSettings):
    """
    Per-user request-rate and token-quota configuration.

    Both defaults are placeholders, not derived from real traffic/cost
    data -- tune via env vars once real usage numbers exist.
    """

    ENABLED: bool = True

    # (a) burst/rate limit: max requests per rolling-minute window.
    REQUESTS_PER_MINUTE: int = 20

    # (b) cost control: max total (input + output) tokens per user per
    # calendar day.
    DAILY_TOKEN_QUOTA: int = 200_000

    @field_validator("REQUESTS_PER_MINUTE", "DAILY_TOKEN_QUOTA")
    @classmethod
    def validate_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Rate-limit values must be greater than zero.")
        return value
