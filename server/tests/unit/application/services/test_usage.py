"""
Unit tests for UsageService.request_token_quota() (review R3).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

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
    with pytest.raises(TokenQuotaExceededError) as raised:
        await service.check_and_enforce(user_id="u1")
    assert raised.value.quota == 1000


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
    repository.record_request_tokens = AsyncMock(return_value=False)
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
