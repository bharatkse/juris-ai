"""
Per-user rate limit and token quota enforcement.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from adapters.observability.logger import get_logger
from application.services.base import BaseService
from config.settings import get_settings
from core.exceptions.rate_limit import RateLimitExceededError, TokenQuotaExceededError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from adapters.persistence.sqlalchemy.repositories.usage_record import (
        UsageRecordRepository,
    )

logger = get_logger(__name__)


class UsageService(BaseService):
    """
    Enforces the per-user request-rate limit and daily token quota,
    and records actual token usage once it's known.

    check_and_enforce() and record() are deliberately separate calls:
    the rate/quota check happens before dispatching to the
    orchestrator (before any tokens are spent), while token usage is
    only known after the LLM call(s) complete. A request that's
    allowed to start can therefore push the day's total slightly past
    the quota once its actual cost is recorded -- inherent to any
    token quota (the exact cost of a response isn't known until it's
    generated), not a bug.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        repository: UsageRecordRepository,
    ) -> None:
        super().__init__(session)
        self._repository = repository

    async def check_and_enforce(self, *, user_id: str) -> None:
        """
        Raise RateLimitExceededError or TokenQuotaExceededError if the
        user has exceeded either limit.

        The request-rate counter is incremented as part of this check
        (an allowed request always counts against the rate limit,
        whether or not it later succeeds) and committed immediately,
        independent of whatever transaction the caller runs afterward.
        """

        settings = get_settings().rate_limit

        if not settings.RATE_LIMIT_ENABLED:
            return

        now = datetime.now(UTC)
        minute_window = now.replace(second=0, microsecond=0)
        day_window = now.replace(hour=0, minute=0, second=0, microsecond=0)

        request_count = await self._repository.increment_request_count(
            user_id=user_id,
            window_start=minute_window,
        )

        await self.commit()

        if request_count > settings.RATE_LIMIT_REQUESTS_PER_MINUTE:
            retry_after_seconds = 60 - now.second

            logger.warning(
                "Rate limit exceeded.",
                extra={
                    "operation": "enforce_usage_limits",
                    "user_id": user_id,
                    "request_count": request_count,
                    "limit": settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
                },
            )

            raise RateLimitExceededError(
                limit=settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
                retry_after_seconds=retry_after_seconds,
            )

        daily_usage = await self._repository.get_daily_token_usage(
            user_id=user_id,
            window_start=day_window,
        )

        if daily_usage >= settings.RATE_LIMIT_DAILY_TOKEN_QUOTA:
            logger.warning(
                "Daily token quota exceeded.",
                extra={
                    "operation": "enforce_usage_limits",
                    "user_id": user_id,
                    "daily_usage": daily_usage,
                    "quota": settings.RATE_LIMIT_DAILY_TOKEN_QUOTA,
                },
            )

            raise TokenQuotaExceededError(
                quota=settings.RATE_LIMIT_DAILY_TOKEN_QUOTA,
                used=daily_usage,
            )

    async def record(
        self,
        *,
        user_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """
        Record actual token usage against the user's daily bucket.

        Best-effort: a failure here must not fail an otherwise-successful
        chat response, so errors are logged and swallowed rather than
        propagated.
        """

        if input_tokens <= 0 and output_tokens <= 0:
            return

        settings = get_settings().rate_limit

        if not settings.RATE_LIMIT_ENABLED:
            return

        now = datetime.now(UTC)
        day_window = now.replace(hour=0, minute=0, second=0, microsecond=0)

        try:
            await self._repository.increment_tokens(
                user_id=user_id,
                window_start=day_window,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            await self.commit()

        except Exception:
            await self.rollback()

            logger.exception(
                "Failed to record token usage.",
                extra={
                    "operation": "record_usage",
                    "user_id": user_id,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
            )
