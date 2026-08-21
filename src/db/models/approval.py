"""
Approval database model.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import ApprovalStatusEnum
from src.db.base import Base
from src.db.mixins import PrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from .action import Action
    from .user import User


class Approval(
    Base,
    PrimaryKeyMixin,
    TimestampMixin,
):
    """
    Persisted human approval request.

    Represents approval for one concrete action.
    """

    __tablename__ = "approvals"
    _id_prefix = "appr"

    action_id: Mapped[str] = mapped_column(
        ForeignKey("actions.id"),
        nullable=False,
        index=True,
    )

    action_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    requested_by: Mapped[str] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    status: Mapped[ApprovalStatusEnum] = mapped_column(
        Enum(
            ApprovalStatusEnum,
            name="approval_status",
        ),
        nullable=False,
        index=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    action: Mapped[Action] = relationship(
        back_populates="approvals",
    )

    requester: Mapped[User] = relationship(
        back_populates="approval_requests",
    )

    @property
    def is_expired(self) -> bool:
        return (
            datetime.now(
                self.expires_at.tzinfo,
            )
            >= self.expires_at
        )

    @property
    def is_waiting(self) -> bool:
        return self.status == ApprovalStatusEnum.WAITING

    @property
    def is_approved(self) -> bool:
        return self.status == ApprovalStatusEnum.APPROVED
