"""
Usage record repository.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.mixins import generate_prefixed_uuid_pk
from adapters.persistence.sqlalchemy.models.usage_record import UsageRecord
from adapters.persistence.sqlalchemy.models.usage_request_record import UsageRequestRecord
from adapters.persistence.sqlalchemy.repositories.base import BaseRepository
from core.utils.datetime import utcnow


class UsageRecordRepository(BaseRepository[UsageRecord]):
    """
    Atomic fixed-window usage counters.

    Uses Postgres INSERT ... ON CONFLICT DO UPDATE (not a
    read-modify-write) so concurrent requests from the same user
    increment the same (user_id, period, window_start) bucket
    correctly instead of racing.
    """

    _model = UsageRecord

    def __init__(self, *, session: AsyncSession) -> None:
        super().__init__(session=session)

    async def increment_request_count(
        self,
        *,
        user_id: str,
        window_start: datetime,
    ) -> int:
        """
        Atomically increment the "minute" request-count bucket and
        return the resulting count.
        """

        request_count, _ = await self._increment(
            user_id=user_id,
            period="minute",
            window_start=window_start,
            request_count_delta=1,
        )
        return request_count

    async def increment_tokens(
        self,
        *,
        user_id: str,
        window_start: datetime,
        input_tokens: int,
        output_tokens: int,
    ) -> int:
        """
        Atomically add to the "day" token-usage bucket; returns the
        bucket's token total (input + output) after the addition.
        """

        _, tokens = await self._increment(
            user_id=user_id,
            period="day",
            window_start=window_start,
            input_tokens_delta=input_tokens,
            output_tokens_delta=output_tokens,
        )
        return tokens

    async def record_request_tokens(
        self,
        *,
        request_id: str,
        user_id: str,
        window_start: datetime,
        input_tokens: int,
        output_tokens: int,
    ) -> int | None:
        """
        Record one request's tokens once: insert its usage_request_records
        row (ON CONFLICT DO NOTHING on request_id) and, only if that row
        is new, add the tokens to the "day" bucket. Returns the day's token
        total after this request, or None when the request was already
        recorded. The caller commits both together.
        """

        now = utcnow()

        statement = (
            pg_insert(UsageRequestRecord)
            .values(
                id=generate_prefixed_uuid_pk(UsageRequestRecord._id_prefix),
                request_id=request_id,
                user_id=user_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["request_id"])
            .returning(UsageRequestRecord.id)
        )

        result = await self._session.execute(statement)

        if result.scalar_one_or_none() is None:
            return None

        return await self.increment_tokens(
            user_id=user_id,
            window_start=window_start,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    async def get_daily_token_usage(
        self,
        *,
        user_id: str,
        window_start: datetime,
    ) -> int:
        """
        Return input_tokens + output_tokens already recorded in the
        given day's bucket (0 if the bucket doesn't exist yet).
        """

        result = await self._session.execute(
            select(
                UsageRecord.input_tokens,
                UsageRecord.output_tokens,
            ).where(
                UsageRecord.user_id == user_id,
                UsageRecord.period == "day",
                UsageRecord.window_start == window_start,
            )
        )

        row = result.first()

        if row is None:
            return 0

        return int(row.input_tokens) + int(row.output_tokens)

    async def _increment(
        self,
        *,
        user_id: str,
        period: str,
        window_start: datetime,
        request_count_delta: int = 0,
        input_tokens_delta: int = 0,
        output_tokens_delta: int = 0,
    ) -> tuple[int, int]:
        """The bucket's request count and token total after the upsert."""

        now = utcnow()

        statement = pg_insert(UsageRecord).values(
            id=generate_prefixed_uuid_pk(UsageRecord._id_prefix),
            user_id=user_id,
            period=period,
            window_start=window_start,
            request_count=request_count_delta,
            input_tokens=input_tokens_delta,
            output_tokens=output_tokens_delta,
            created_at=now,
            updated_at=now,
        )

        upsert = statement.on_conflict_do_update(
            index_elements=["user_id", "period", "window_start"],
            set_={
                "request_count": UsageRecord.request_count + request_count_delta,
                "input_tokens": UsageRecord.input_tokens + input_tokens_delta,
                "output_tokens": UsageRecord.output_tokens + output_tokens_delta,
                "updated_at": now,
            },
        ).returning(
            UsageRecord.request_count,
            UsageRecord.input_tokens + UsageRecord.output_tokens,
        )

        request_count, tokens = (await self._session.execute(upsert)).one()

        return int(request_count), int(tokens)
