"""
scripts/usage_percentiles.py --suggest: recommended token quotas from the
observed p99s (review R13 follow-up).

- TOKEN_QUOTA_PER_REQUEST: p99 tokens per request × 1.5, rounded up to the
  next 10,000.
- TOKEN_QUOTA_DAILY: p99 tokens per user per day × 2, and never below the
  suggested per-request quota (the server refuses to start otherwise).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "usage_percentiles.py"


def _script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("usage_percentiles", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve the module through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("p99_request", "expected"),
    [
        (20_000, 30_000),  # 30,000 exactly: already a multiple
        (20_001, 40_000),  # 30,001.5 -> next 10k
        (1, 10_000),
        (66_667, 110_000),  # 100,000.5 -> 110,000
    ],
)
def test_the_per_request_suggestion_is_p99_times_1_5_rounded_up_to_10k(
    p99_request: int, expected: int
) -> None:
    suggestion = _script().suggest_quotas(p99_request=p99_request, p99_user_day=10**9)

    assert suggestion is not None
    assert suggestion.per_request == expected


def test_the_daily_suggestion_is_twice_the_p99_per_user_day() -> None:
    suggestion = _script().suggest_quotas(p99_request=20_000, p99_user_day=150_000)

    assert suggestion is not None
    assert suggestion.daily == 300_000


def test_the_daily_suggestion_is_never_below_the_per_request_one() -> None:
    suggestion = _script().suggest_quotas(p99_request=60_000, p99_user_day=20_000)

    assert suggestion is not None
    assert suggestion.per_request == 90_000
    assert suggestion.daily == 90_000


@pytest.mark.parametrize(("p99_request", "p99_user_day"), [(None, 10), (10, None), (0, 0)])
def test_no_suggestion_without_usage_data(
    p99_request: int | None, p99_user_day: int | None
) -> None:
    assert _script().suggest_quotas(p99_request=p99_request, p99_user_day=p99_user_day) is None
