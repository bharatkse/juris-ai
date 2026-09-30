"""
Report token usage percentiles, to size the token quotas (review R13
follow-up): TOKEN_QUOTA_PER_REQUEST and TOKEN_QUOTA_DAILY.

Reads usage_request_records (one row per chat request, written once
whether the request succeeded or not) and prints p50/p95/p99/max of:
- tokens per request (input + output), and
- tokens per user per day (UTC days, the quota's day),
over the last N days. Read-only: runs in a READ ONLY transaction as the
app's runtime role.

With --suggest it also prints recommended quotas (suggest_quotas()) and,
for the current and the suggested values, how many of those past
requests and user-days would have gone over them.

Usage (from server/, Postgres on the host):

    DB_HOST=localhost PYTHONPATH=src poetry run python \\
        scripts/usage_percentiles.py [--days 7] [--suggest]
"""

from __future__ import annotations

import argparse
import asyncio
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

# Headroom over the observed p99s.
PER_REQUEST_HEADROOM = 1.5
DAILY_HEADROOM = 2
PER_REQUEST_ROUNDING = 10_000

_STATS = """
    count(*) AS n,
    percentile_disc(0.50) WITHIN GROUP (ORDER BY tokens) AS p50,
    percentile_disc(0.95) WITHIN GROUP (ORDER BY tokens) AS p95,
    percentile_disc(0.99) WITHIN GROUP (ORDER BY tokens) AS p99,
    max(tokens) AS max
"""

_REQUESTS = """
    SELECT input_tokens + output_tokens AS tokens
    FROM usage_request_records
    WHERE created_at >= :since
"""

_USER_DAYS = """
    SELECT sum(input_tokens + output_tokens) AS tokens
    FROM usage_request_records
    WHERE created_at >= :since
    GROUP BY user_id, date_trunc('day', created_at AT TIME ZONE 'UTC')
"""

PER_REQUEST = text(f"SELECT {_STATS} FROM ({_REQUESTS}) AS requests")
PER_USER_DAY = text(f"SELECT {_STATS} FROM ({_USER_DAYS}) AS user_days")

# How many past requests / user-days went over a given quota. A request
# over the per-request quota would have been refused; a user-day over the
# daily quota would have had its later requests refused.
REQUESTS_OVER = text(f"SELECT count(*) FROM ({_REQUESTS}) AS requests WHERE tokens > :quota")
USER_DAYS_OVER = text(f"SELECT count(*) FROM ({_USER_DAYS}) AS user_days WHERE tokens > :quota")


@dataclass(frozen=True, slots=True)
class QuotaSuggestion:
    per_request: int
    daily: int


def suggest_quotas(*, p99_request: int | None, p99_user_day: int | None) -> QuotaSuggestion | None:
    """
    TOKEN_QUOTA_PER_REQUEST: p99 tokens per request × 1.5, rounded up to
    the next 10,000. TOKEN_QUOTA_DAILY: p99 tokens per user per day × 2,
    but never below the suggested per-request quota (the server refuses to
    start with a daily quota below the per-request one). None without
    usage data.
    """

    if not p99_request or not p99_user_day:
        return None

    per_request = (
        math.ceil(p99_request * PER_REQUEST_HEADROOM / PER_REQUEST_ROUNDING) * PER_REQUEST_ROUNDING
    )
    daily = max(p99_user_day * DAILY_HEADROOM, per_request)

    return QuotaSuggestion(per_request=per_request, daily=daily)


def _row(label: str, row: Sequence[int | None], quota: int) -> str:
    n, p50, p95, p99, largest = row
    if not n:
        return f"| {label} | 0 | - | - | - | - | {quota:,} |"
    return f"| {label} | {n:,} | {p50:,} | {p95:,} | {p99:,} | {largest:,} | {quota:,} |"


async def main(days: int, *, suggest: bool) -> None:
    from adapters.persistence.sqlalchemy.session import session_factory
    from config.settings import get_settings

    since = datetime.now(UTC) - timedelta(days=days)
    quotas = get_settings().rate_limit

    async with session_factory() as session:
        await session.execute(text("SET TRANSACTION READ ONLY"))
        per_request = tuple((await session.execute(PER_REQUEST, {"since": since})).one())
        per_user_day = tuple((await session.execute(PER_USER_DAY, {"since": since})).one())

        suggestion = suggest_quotas(p99_request=per_request[3], p99_user_day=per_user_day[3])
        over: dict[str, tuple[int, int]] = {}

        if suggest and suggestion is not None:
            for label, per_request_quota, daily_quota in (
                ("Current", quotas.TOKEN_QUOTA_PER_REQUEST, quotas.TOKEN_QUOTA_DAILY),
                ("Suggested", suggestion.per_request, suggestion.daily),
            ):
                requests_over = (
                    await session.execute(
                        REQUESTS_OVER, {"since": since, "quota": per_request_quota}
                    )
                ).scalar_one()
                days_over = (
                    await session.execute(USER_DAYS_OVER, {"since": since, "quota": daily_quota})
                ).scalar_one()
                over[label] = (int(requests_over), int(days_over))

        await session.rollback()

    print(f"Token usage since {since:%Y-%m-%d %H:%M} UTC (last {days} days)\n")
    print("| Scope | Samples | p50 | p95 | p99 | max | Current quota |")
    print("|---|---|---|---|---|---|---|")
    print(_row("Per request", per_request, quotas.TOKEN_QUOTA_PER_REQUEST))
    print(_row("Per user per day", per_user_day, quotas.TOKEN_QUOTA_DAILY))

    if not suggest:
        return

    print()
    if suggestion is None:
        print("No usage recorded in this window: nothing to suggest yet.")
        return

    print("Suggested (p99 per request × 1.5, rounded up to 10k; p99 per user-day × 2):\n")
    print(f"TOKEN_QUOTA_PER_REQUEST={suggestion.per_request}")
    print(f"TOKEN_QUOTA_DAILY={suggestion.daily}\n")
    print(
        f"| Quotas | Per request | Daily | Requests over (of {per_request[0]:,}) "
        f"| User-days over (of {per_user_day[0]:,}) |"
    )
    print("|---|---|---|---|---|")
    for label, per_request_quota, daily_quota in (
        ("Current", quotas.TOKEN_QUOTA_PER_REQUEST, quotas.TOKEN_QUOTA_DAILY),
        ("Suggested", suggestion.per_request, suggestion.daily),
    ):
        requests_over, days_over = over[label]
        print(
            f"| {label} | {per_request_quota:,} | {daily_quota:,} "
            f"| {requests_over:,} | {days_over:,} |"
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--days", type=int, default=7, help="look-back window (default 7)")
    parser.add_argument(
        "--suggest",
        action="store_true",
        help="print recommended quotas and how many past requests/days each would refuse",
    )
    args = parser.parse_args()
    if args.days <= 0:
        parser.error("--days must be greater than zero")
    return args


if __name__ == "__main__":
    arguments = _parse_args()
    asyncio.run(main(arguments.days, suggest=arguments.suggest))
