"""
Report token usage percentiles, to size the token quotas (review R13
follow-up): TOKEN_QUOTA_PER_REQUEST and TOKEN_QUOTA_DAILY.

Reads usage_request_records (one row per chat request, written once
whether the request succeeded or not) and prints p50/p95/p99/max of:
- tokens per request (input + output), and
- tokens per user per day (UTC days, the quota's day),
over the last N days. Read-only: runs in a READ ONLY transaction as the
app's runtime role.

Usage (from server/, Postgres on the host):

    DB_HOST=localhost PYTHONPATH=src poetry run python \\
        scripts/usage_percentiles.py [--days 7]
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from adapters.persistence.sqlalchemy.session import session_factory
from config.settings import get_settings

_STATS = """
    count(*) AS n,
    percentile_disc(0.50) WITHIN GROUP (ORDER BY tokens) AS p50,
    percentile_disc(0.95) WITHIN GROUP (ORDER BY tokens) AS p95,
    percentile_disc(0.99) WITHIN GROUP (ORDER BY tokens) AS p99,
    max(tokens) AS max
"""

PER_REQUEST = text(
    f"""
    SELECT {_STATS}
    FROM (
        SELECT input_tokens + output_tokens AS tokens
        FROM usage_request_records
        WHERE created_at >= :since
    ) AS requests
    """
)

PER_USER_DAY = text(
    f"""
    SELECT {_STATS}
    FROM (
        SELECT sum(input_tokens + output_tokens) AS tokens
        FROM usage_request_records
        WHERE created_at >= :since
        GROUP BY user_id, date_trunc('day', created_at AT TIME ZONE 'UTC')
    ) AS user_days
    """
)


def _row(label: str, row: Sequence[int | None], quota: int) -> str:
    n, p50, p95, p99, largest = row
    if not n:
        return f"| {label} | 0 | - | - | - | - | {quota:,} |"
    return f"| {label} | {n:,} | {p50:,} | {p95:,} | {p99:,} | {largest:,} | {quota:,} |"


async def main(days: int) -> None:
    since = datetime.now(UTC) - timedelta(days=days)
    quotas = get_settings().rate_limit

    async with session_factory() as session:
        await session.execute(text("SET TRANSACTION READ ONLY"))
        per_request = tuple((await session.execute(PER_REQUEST, {"since": since})).one())
        per_user_day = tuple((await session.execute(PER_USER_DAY, {"since": since})).one())
        await session.rollback()

    print(f"Token usage since {since:%Y-%m-%d %H:%M} UTC (last {days} days)\n")
    print("| Scope | Samples | p50 | p95 | p99 | max | Current quota |")
    print("|---|---|---|---|---|---|---|")
    print(_row("Per request", per_request, quotas.TOKEN_QUOTA_PER_REQUEST))
    print(_row("Per user per day", per_user_day, quotas.TOKEN_QUOTA_DAILY))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--days", type=int, default=7, help="look-back window (default 7)")
    args = parser.parse_args()
    if args.days <= 0:
        parser.error("--days must be greater than zero")
    return args


if __name__ == "__main__":
    asyncio.run(main(_parse_args().days))
