"""
Reusable assertion helpers.
"""

from __future__ import annotations

import re
from typing import Any

UUID_PATTERN = re.compile(r"^[a-f0-9]{32}$")


def assert_prefixed_uuid(
    value: str,
    *,
    prefix: str,
) -> None:
    """
    Assert that a value matches the expected prefixed UUID format.

    Example:
        user_2f8a7d4b5e3d41f59c6d0d7c4e9a1234
    """

    assert value, "Identifier must not be empty."

    expected_prefix = f"{prefix}_"

    assert value.startswith(
        expected_prefix,
    ), f"Expected identifier to start with " f"{expected_prefix!r}, got {value!r}."

    uuid = value.removeprefix(expected_prefix)

    assert UUID_PATTERN.fullmatch(
        uuid,
    ), f"Expected a 32-character hexadecimal UUID, " f"got {uuid!r}."


def assert_not_none(
    value: Any,
) -> None:
    """
    Assert that a value is not None.
    """

    assert value is not None


def assert_is_none(
    value: Any,
) -> None:
    """
    Assert that a value is None.
    """

    assert value is None
