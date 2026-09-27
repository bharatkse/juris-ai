"""
Container-only regression guard for the Redis host setting.

Inside the api container, "localhost" is the container itself, not the
redis service -- a REDIS_HOST left at (or defaulting to) localhost there
breaks every request that touches the cache. Host-side tests can't catch
this: the published localhost:6379 port works from the host. Skipped
everywhere except inside a Docker container.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from config import get_settings

pytestmark = pytest.mark.skipif(
    not Path("/.dockerenv").exists(),
    reason="Only meaningful inside a Docker container (/.dockerenv not found).",
)


def test_redis_host_is_not_loopback_inside_container() -> None:
    """
    It should not resolve REDIS_HOST to a loopback address in a container.
    """

    host = get_settings().security.REDIS_HOST

    assert host not in {"localhost", "127.0.0.1"}, (
        f"REDIS_HOST resolved to {host!r} inside a container, which is the "
        "container itself -- it should be the redis service name."
    )
