"""
Per-request token usage ledger.

One row per request whose LLM calls used tokens (review R19). The unique
request_id makes recording idempotent: the row is inserted with
ON CONFLICT DO NOTHING, and the day bucket in usage_records is added to
only when that insert happened, so a request's tokens are never counted
twice. See UsageRecordRepository.record_request_tokens().
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from adapters.persistence.sqlalchemy.base import Base
from adapters.persistence.sqlalchemy.mixins import PrimaryKeyMixin, TimestampMixin


class UsageRequestRecord(
    Base,
    PrimaryKeyMixin,
    TimestampMixin,
):
    """
    The tokens one request's LLM calls used, whatever the request's
    outcome (answered, failed, refused by the quota, cancelled).
    """

    __tablename__ = "usage_request_records"
    _id_prefix = "usrq"

    request_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    input_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    output_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
