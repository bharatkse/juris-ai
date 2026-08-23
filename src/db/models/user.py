"""
User ORM model.
"""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import GenderEnum
from src.db.base import Base
from src.db.mixins import PrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from .agent_action import AgentAction
    from .approval import Approval
    from .conversation import Conversation


class User(PrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    _id_prefix = "user"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    first_name: Mapped[str] = mapped_column(String(50), nullable=True)
    last_name: Mapped[str] = mapped_column(String(50), nullable=True)
    gender: Mapped[GenderEnum] = mapped_column(String(10), nullable=True)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=True)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=True)
    is_active: Mapped[Boolean] = mapped_column(Boolean, default=True)

    conversations: Mapped[list["Conversation"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    agent_actions: Mapped[list["AgentAction"]] = relationship(
        back_populates="user",
    )

    requested_approvals: Mapped[list["Approval"]] = relationship(
        foreign_keys="Approval.requested_by",
        back_populates="requester",
    )

    approved_approvals: Mapped[list["Approval"]] = relationship(
        foreign_keys="Approval.approved_by",
        back_populates="approver",
    )

    def __repr__(self) -> str:
        return f"User(" f"id={self.id!r}, " f"email={self.email!r}" f")"

    @property
    def full_name(self) -> str:
        return " ".join(filter(None, [self.first_name, self.last_name]))
