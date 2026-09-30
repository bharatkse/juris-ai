"""
Token quota settings (review R13 follow-up): TOKEN_QUOTA_PER_REQUEST and
TOKEN_QUOTA_DAILY, with the old RATE_LIMIT_* names still accepted, and a
daily quota that can't be below the per-request one.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from config.rate_limit import RateLimitSettings

_QUOTA_ENV = (
    "TOKEN_QUOTA_PER_REQUEST",
    "TOKEN_QUOTA_DAILY",
    "RATE_LIMIT_REQUEST_TOKEN_QUOTA",
    "RATE_LIMIT_DAILY_TOKEN_QUOTA",
)


@pytest.fixture(autouse=True)
def _no_quota_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _QUOTA_ENV:
        monkeypatch.delenv(name, raising=False)


def _settings(**values: int) -> RateLimitSettings:
    return RateLimitSettings(_env_file=None, **values)  # type: ignore[call-arg]


def test_the_default_quotas() -> None:
    settings = _settings()

    assert settings.TOKEN_QUOTA_PER_REQUEST == 100_000
    assert settings.TOKEN_QUOTA_DAILY == 2_000_000


def test_the_quotas_are_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKEN_QUOTA_PER_REQUEST", "5000")
    monkeypatch.setenv("TOKEN_QUOTA_DAILY", "50000")

    settings = _settings()

    assert settings.TOKEN_QUOTA_PER_REQUEST == 5000
    assert settings.TOKEN_QUOTA_DAILY == 50000


def test_the_old_variable_names_are_still_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_REQUEST_TOKEN_QUOTA", "6000")
    monkeypatch.setenv("RATE_LIMIT_DAILY_TOKEN_QUOTA", "60000")

    settings = _settings()

    assert settings.TOKEN_QUOTA_PER_REQUEST == 6000
    assert settings.TOKEN_QUOTA_DAILY == 60000


def test_a_daily_quota_below_the_per_request_quota_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TOKEN_QUOTA_PER_REQUEST", "100000")
    monkeypatch.setenv("TOKEN_QUOTA_DAILY", "99999")

    with pytest.raises(ValidationError, match="TOKEN_QUOTA_DAILY .* TOKEN_QUOTA_PER_REQUEST"):
        _settings()


def test_a_daily_quota_equal_to_the_per_request_quota_is_allowed() -> None:
    settings = _settings(TOKEN_QUOTA_PER_REQUEST=1000, TOKEN_QUOTA_DAILY=1000)

    assert settings.TOKEN_QUOTA_DAILY == settings.TOKEN_QUOTA_PER_REQUEST


@pytest.mark.parametrize("name", ["TOKEN_QUOTA_PER_REQUEST", "TOKEN_QUOTA_DAILY"])
def test_a_quota_must_be_positive(name: str) -> None:
    with pytest.raises(ValidationError):
        _settings(**{name: 0})
