"""
Unit tests for UsageService.request_token_quota() (review R3).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from application.services import usage as usage_module
from application.services.usage import UsageService
from config.settings import get_settings
from core.exceptions.rate_limit import TokenQuotaExceededError


def _service() -> UsageService:
    return UsageService(session=AsyncMock(), repository=MagicMock())


def test_request_token_quota_comes_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings().rate_limit
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "TOKEN_QUOTA_PER_REQUEST", 1234)

    assert _service().request_token_quota() == 1234


@pytest.mark.asyncio
async def test_the_daily_quota_comes_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings().rate_limit
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "TOKEN_QUOTA_PER_REQUEST", 500)
    monkeypatch.setattr(settings, "TOKEN_QUOTA_DAILY", 1000)
    repository = MagicMock()
    repository.increment_request_count = AsyncMock(return_value=1)
    service = UsageService(session=AsyncMock(), repository=repository)

    repository.get_daily_token_usage = AsyncMock(return_value=999)
    await service.check_and_enforce(user_id="u1")

    repository.get_daily_token_usage = AsyncMock(return_value=1000)
    with (
        patch.object(usage_module.metrics, "record_token_quota_rejection") as rejected,
        pytest.raises(TokenQuotaExceededError) as raised,
    ):
        await service.check_and_enforce(user_id="u1")
    assert raised.value.quota == 1000
    rejected.assert_called_once_with(quota="daily")


def test_no_request_token_quota_when_rate_limiting_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings().rate_limit
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)

    assert _service().request_token_quota() is None


@pytest.mark.asyncio
async def test_record_writes_once_per_request_id_and_never_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    R19: record() hands the request id to the idempotent repository write
    and commits; a write that fails is logged, rolled back and swallowed.
    """

    monkeypatch.setattr(get_settings().rate_limit, "RATE_LIMIT_ENABLED", True)
    repository = MagicMock()
    repository.record_request_tokens = AsyncMock(return_value=None)
    session = AsyncMock()
    service = UsageService(session=session, repository=repository)

    await service.record(user_id="u1", request_id="r1", input_tokens=10, output_tokens=2)

    assert repository.record_request_tokens.await_args.kwargs["request_id"] == "r1"
    session.commit.assert_awaited_once()

    repository.record_request_tokens.side_effect = RuntimeError("db down")
    await service.record(user_id="u1", request_id="r2", input_tokens=10, output_tokens=2)
    session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_skips_a_request_that_used_no_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings().rate_limit, "RATE_LIMIT_ENABLED", True)
    repository = MagicMock()
    repository.record_request_tokens = AsyncMock()

    await UsageService(session=AsyncMock(), repository=repository).record(
        user_id="u1", request_id="r1", input_tokens=0, output_tokens=0
    )

    repository.record_request_tokens.assert_not_awaited()


# Quota tuning: a user crossing 80% of the daily quota is logged and
# counted once, from the day's total the recording write returned.


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("day_total_after", "tokens", "crossed"),
    [
        (800, 100, True),  # 700 -> 800: reaches 80% exactly
        (850, 100, True),  # 750 -> 850
        (799, 100, False),  # still below
        (900, 50, False),  # already above before this request
        (1200, 500, True),  # 700 -> 1200: past the quota in one step, still crossed once
    ],
)
async def test_crossing_80_percent_of_the_daily_quota_is_reported_once(
    monkeypatch: pytest.MonkeyPatch, day_total_after: int, tokens: int, crossed: bool
) -> None:
    settings = get_settings().rate_limit
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "TOKEN_QUOTA_PER_REQUEST", 500)
    monkeypatch.setattr(settings, "TOKEN_QUOTA_DAILY", 1000)
    repository = MagicMock()
    repository.record_request_tokens = AsyncMock(return_value=day_total_after)
    service = UsageService(session=AsyncMock(), repository=repository)

    with (
        patch.object(usage_module.metrics, "record_token_quota_threshold_crossed") as metric,
        patch.object(usage_module, "logger") as log,
    ):
        await service.record(
            user_id="u1", request_id="r1", input_tokens=tokens - 10, output_tokens=10
        )

    assert metric.called is crossed
    if crossed:
        metric.assert_called_once_with(threshold="0.8")
        extra = log.info.call_args.kwargs["extra"]
        assert extra["user_id"] == "u1"
        assert extra["daily_tokens"] == day_total_after
        assert extra["quota"] == 1000


@pytest.mark.asyncio
async def test_a_request_already_recorded_is_not_reported_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings().rate_limit, "RATE_LIMIT_ENABLED", True)
    repository = MagicMock()
    repository.record_request_tokens = AsyncMock(return_value=None)

    with patch.object(usage_module.metrics, "record_token_quota_threshold_crossed") as metric:
        await UsageService(session=AsyncMock(), repository=repository).record(
            user_id="u1", request_id="r1", input_tokens=10, output_tokens=2
        )

    metric.assert_not_called()
