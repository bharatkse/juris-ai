"""
Datetime testing helpers.
"""

from __future__ import annotations

from datetime import datetime, timedelta


def assert_datetime_close(
    actual: datetime,
    expected: datetime,
    *,
    tolerance: timedelta = timedelta(seconds=1),
) -> None:
    """
    Assert that two datetimes are within a tolerance.
    """

    delta = abs(actual - expected)

    assert delta <= tolerance, (
        f"Expected datetimes to differ by at most " f"{tolerance}, but difference was {delta}."
    )


def assert_datetime_between(
    value: datetime,
    *,
    start: datetime,
    end: datetime,
) -> None:
    """
    Assert that a datetime falls within the given range.
    """

    assert start <= value <= end, f"Expected {value!r} to be between " f"{start!r} and {end!r}."
