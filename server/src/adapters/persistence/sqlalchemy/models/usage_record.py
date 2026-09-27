"""
Per-user usage record persistence model.

Fixed-window counters for request-rate limiting and token-quota
enforcement. One row per (user, period, window_start) bucket -- see
application/services/usage.py for the read/increment logic.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from adapters.persistence.sqlalchemy.base import Base
from adapters.persistence.sqlalchemy.mixins import PrimaryKeyMixin, TimestampMixin


class UsageRecord(
    Base,
    PrimaryKeyMixin,
    TimestampMixin,
):
    """
    One fixed-window usage counter bucket for one user.

    ``period`` + ``window_start`` together identify the bucket:
    period="minute" buckets back the request-rate limit, period="day"
    buckets back the daily token quota. The unique constraint is what
    makes atomic upsert-increment (INSERT ... ON CONFLICT DO UPDATE)
    correct under concurrent requests from the same user.
    """

    __tablename__ = "usage_records"
    _id_prefix = "usge"

    user_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    period: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    request_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    input_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    output_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "period",
            "window_start",
            name="uq_usage_records_user_id_period_window_start",
        ),
    )
