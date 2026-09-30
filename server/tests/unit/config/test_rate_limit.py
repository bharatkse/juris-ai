"""
Token quota settings (review R13 follow-up): TOKEN_QUOTA_PER_REQUEST and
TOKEN_QUOTA_DAILY, with the old RATE_LIMIT_* names still accepted but
deprecated (a new name wins), and a daily quota that can't be below the
per-request one.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from config.rate_limit import DeprecatedSetting, RateLimitSettings

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


# The old names are deprecated: each one read is reported (and logged at
# startup, main.log_deprecated_settings()); a new name set anywhere wins.


def test_an_old_name_alone_is_used_and_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_DAILY_TOKEN_QUOTA", "300000")

    settings = _settings()

    assert settings.TOKEN_QUOTA_DAILY == 300000
    assert settings.deprecated_names() == (
        DeprecatedSetting(
            old_name="RATE_LIMIT_DAILY_TOKEN_QUOTA",
            new_name="TOKEN_QUOTA_DAILY",
            new_name_also_set=False,
        ),
    )


def test_new_names_alone_report_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKEN_QUOTA_PER_REQUEST", "5000")
    monkeypatch.setenv("TOKEN_QUOTA_DAILY", "50000")

    assert _settings().deprecated_names() == ()


def test_the_new_name_wins_over_the_old_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_REQUEST_TOKEN_QUOTA", "6000")
    monkeypatch.setenv("TOKEN_QUOTA_PER_REQUEST", "5000")

    settings = _settings()

    assert settings.TOKEN_QUOTA_PER_REQUEST == 5000
    assert settings.deprecated_names() == (
        DeprecatedSetting(
            old_name="RATE_LIMIT_REQUEST_TOKEN_QUOTA",
            new_name="TOKEN_QUOTA_PER_REQUEST",
            new_name_also_set=True,
        ),
    )


def test_the_new_name_in_the_env_file_wins_over_the_old_one_in_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("TOKEN_QUOTA_DAILY=400000\n")
    monkeypatch.setenv("RATE_LIMIT_DAILY_TOKEN_QUOTA", "300000")

    settings = RateLimitSettings(_env_file=env_file)  # type: ignore[call-arg]

    assert settings.TOKEN_QUOTA_DAILY == 400000
    assert settings.deprecated_names()[0].new_name_also_set is True


def test_an_old_name_in_the_env_file_is_used_and_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("RATE_LIMIT_DAILY_TOKEN_QUOTA=300000\n")

    settings = RateLimitSettings(_env_file=env_file)  # type: ignore[call-arg]

    assert settings.TOKEN_QUOTA_DAILY == 300000
    assert [d.old_name for d in settings.deprecated_names()] == ["RATE_LIMIT_DAILY_TOKEN_QUOTA"]
