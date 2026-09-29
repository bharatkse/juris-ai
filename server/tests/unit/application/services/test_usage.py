"""
Unit tests for UsageService.request_token_quota() (review R3).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from application.services.usage import UsageService
from config.settings import get_settings


def _service() -> UsageService:
    return UsageService(session=AsyncMock(), repository=MagicMock())


def test_the_default_request_token_quota_is_below_the_daily_quota() -> None:
    from config.rate_limit import RateLimitSettings

    settings = RateLimitSettings()

    assert settings.RATE_LIMIT_REQUEST_TOKEN_QUOTA == 100_000
    assert settings.RATE_LIMIT_REQUEST_TOKEN_QUOTA < settings.RATE_LIMIT_DAILY_TOKEN_QUOTA


def test_the_request_token_quota_must_be_positive() -> None:
    from config.rate_limit import RateLimitSettings

    with pytest.raises(ValueError):
        RateLimitSettings(RATE_LIMIT_REQUEST_TOKEN_QUOTA=0)


def test_request_token_quota_comes_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings().rate_limit
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_REQUEST_TOKEN_QUOTA", 1234)

    assert _service().request_token_quota() == 1234


def test_no_request_token_quota_when_rate_limiting_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = get_settings().rate_limit
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", False)

    assert _service().request_token_quota() is None
