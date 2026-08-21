"""
Action database model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.enums import ActionTypeEnum
from src.db.base import Base
from src.db.mixins import PrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from .approval import Approval
    from .conversation_event import ConversationEvent


class Action(
    Base,
    PrimaryKeyMixin,
    TimestampMixin,
):
    """
    Persisted executable action proposed during execution.

    An action may target a tool, another agent, or another
    execution capability.
    """

    __tablename__ = "actions"
    _id_prefix = "actn"

    event_id: Mapped[str] = mapped_column(
        ForeignKey("conversation_events.id"),
        nullable=False,
        index=True,
    )

    action_type: Mapped[ActionTypeEnum] = mapped_column(
        Enum(
            ActionTypeEnum,
            name="action_type",
        ),
        nullable=False,
        index=True,
    )

    agent_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    tool_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    target_agent_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    arguments: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    reason: Mapped[str] = mapped_column(
        String(10_000),
        nullable=False,
        default="",
    )

    resource_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    event: Mapped[ConversationEvent] = relationship(
        back_populates="actions",
    )

    approvals: Mapped[list[Approval]] = relationship(
        back_populates="action",
    )
