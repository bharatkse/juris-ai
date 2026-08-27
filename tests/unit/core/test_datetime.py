"""
Unit tests for datetime utilities.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.utils.datetime import utcnow


def test_utcnow_returns_timezone_aware_datetime() -> None:
    """
    It should return a timezone-aware UTC datetime.
    """

    value = utcnow()

    assert isinstance(
        value,
        datetime,
    )

    assert value.tzinfo == UTC


def test_utcnow_returns_current_time() -> None:
    """
    It should return the current UTC time.
    """

    before = datetime.now(
        UTC,
    )

    value = utcnow()

    after = datetime.now(
        UTC,
    )

    assert before <= value <= after
