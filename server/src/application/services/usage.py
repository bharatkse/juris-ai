"""
Per-user rate limit and token quota enforcement.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from adapters.observability.logger import get_logger
from adapters.observability.metrics import metrics
from adapters.persistence.sqlalchemy.repositories.usage_record import (
    UsageRecordRepository,
)
from application.services.base import BaseService
from config.settings import get_settings
from core.exceptions.rate_limit import RateLimitExceededError, TokenQuotaExceededError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

# Share of the daily token quota at which a user's day is reported (an INFO
# log and juris_ai_token_quota_threshold_crossings_total), to see how close
# real traffic runs to the quota before anyone is refused.
DAILY_QUOTA_REPORT_FRACTION = 0.8


class UsageService(BaseService):
    """
    Enforces the per-user request-rate limit and daily token quota,
    provides the per-request token quota, and records actual token
    usage once it's known.

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
        record_session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        super().__init__(session)
        self._repository = repository
        # record() writes on a session of its own when given a factory,
        # so it can finish after the request's session is gone (a client
        # that disconnected mid-stream). Without one it uses `session`.
        self._record_session_factory = record_session_factory

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

        if daily_usage >= settings.TOKEN_QUOTA_DAILY:
            logger.warning(
                "Daily token quota exceeded.",
                extra={
                    "operation": "enforce_usage_limits",
                    "user_id": user_id,
                    "daily_usage": daily_usage,
                    "quota": settings.TOKEN_QUOTA_DAILY,
                },
            )

            metrics.record_token_quota_rejection(quota="daily")

            raise TokenQuotaExceededError(
                quota=settings.TOKEN_QUOTA_DAILY,
                used=daily_usage,
            )

    def request_token_quota(self) -> int | None:
        """
        The most tokens one request may use (TOKEN_QUOTA_PER_REQUEST),
        or None when rate limiting is off.

        The per-request counterpart of check_and_enforce()'s daily quota,
        and enforced the same way: before the tokens are spent. The daily
        quota is checked once before a request starts; this one before
        each of the request's LLM calls (core.usage, set by ChatService).
        """

        settings = get_settings().rate_limit

        if not settings.RATE_LIMIT_ENABLED:
            return None

        return settings.TOKEN_QUOTA_PER_REQUEST

    async def record(
        self,
        *,
        user_id: str,
        request_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """
        Record one request's actual token usage against the user's daily
        bucket, exactly once per request_id (review R19): a second call
        for the same request changes nothing (usage_request_records).

        Best-effort: a failure here must not fail an otherwise-successful
        chat response, so errors are logged and swallowed rather than
        propagated. Commits its own write, on its own session when the
        service has a record_session_factory.
        """

        if input_tokens <= 0 and output_tokens <= 0:
            return

        settings = get_settings().rate_limit

        if not settings.RATE_LIMIT_ENABLED:
            return

        now = datetime.now(UTC)
        day_window = now.replace(hour=0, minute=0, second=0, microsecond=0)

        try:
            if self._record_session_factory is None:
                await self._record_request_tokens(
                    session=self.session,
                    repository=self._repository,
                    user_id=user_id,
                    request_id=request_id,
                    day_window=day_window,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    daily_quota=settings.TOKEN_QUOTA_DAILY,
                )
            else:
                async with self._record_session_factory() as session:
                    await self._record_request_tokens(
                        session=session,
                        repository=UsageRecordRepository(session=session),
                        user_id=user_id,
                        request_id=request_id,
                        day_window=day_window,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        daily_quota=settings.TOKEN_QUOTA_DAILY,
                    )

        except Exception:
            if self._record_session_factory is None:
                await self.rollback()

            logger.exception(
                "Failed to record token usage.",
                extra={
                    "operation": "record_usage",
                    "user_id": user_id,
                    "request_id": request_id,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                },
            )

    @staticmethod
    async def _record_request_tokens(
        *,
        session: AsyncSession,
        repository: UsageRecordRepository,
        user_id: str,
        request_id: str,
        day_window: datetime,
        input_tokens: int,
        output_tokens: int,
        daily_quota: int,
    ) -> None:
        day_total = await repository.record_request_tokens(
            request_id=request_id,
            user_id=user_id,
            window_start=day_window,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        await session.commit()

        if day_total is None:
            logger.info(
                "Token usage already recorded for this request; not counted again.",
                extra={"operation": "record_usage", "request_id": request_id},
            )
            return

        # The day's total before and after this request, both from the one
        # atomic write, so exactly one request reports the crossing.
        threshold = DAILY_QUOTA_REPORT_FRACTION * daily_quota
        before = day_total - input_tokens - output_tokens

        if before < threshold <= day_total:
            metrics.record_token_quota_threshold_crossed(threshold="0.8")
            logger.info(
                "User crossed 80% of the daily token quota.",
                extra={
                    "operation": "record_usage",
                    "user_id": user_id,
                    "daily_tokens": day_total,
                    "quota": daily_quota,
                },
            )
