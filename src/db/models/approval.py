"""
Approval database model.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON as JSONB
from sqlalchemy import Enum as PgEnum
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.dto.approval import ApprovalRequestDTO, ApprovalResponseDTO
from src.core.enums import ApprovalDecisionEnum, ApprovalStatusEnum
from src.db.base import Base
from src.db.mixins import PrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from .agent_action import AgentAction
    from .user import User


class Approval(
    Base,
    PrimaryKeyMixin,
    TimestampMixin,
):
    """
    Persisted human approval request.

    An approval represents one approval cycle for one concrete
    agent action.

    An agent action may have multiple approval cycles when a human
    edits or rejects a previous approval request.
    """

    __tablename__ = "approvals"
    _id_prefix = "appr"

    # ------------------------------------------------------------------
    # Action
    # ------------------------------------------------------------------

    agent_action_id: Mapped[str] = mapped_column(
        ForeignKey("agent_actions.id"),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    status: Mapped[ApprovalStatusEnum] = mapped_column(
        PgEnum(
            ApprovalStatusEnum,
            name="approval_status",
        ),
        nullable=False,
        default=ApprovalStatusEnum.WAITING,
        index=True,
    )

    # ------------------------------------------------------------------
    # Requester
    # ------------------------------------------------------------------

    requested_by: Mapped[str] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------
    # Decision
    # ------------------------------------------------------------------

    approved_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    decision_type: Mapped[ApprovalDecisionEnum | None] = mapped_column(
        PgEnum(
            ApprovalDecisionEnum,
            name="approval_decision_type",
        ),
        nullable=True,
    )

    decision_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Edited action
    # ------------------------------------------------------------------

    edited_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    edited_fingerprint: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Timing
    # ------------------------------------------------------------------

    expires_at: Mapped[datetime] = mapped_column(
        nullable=False,
        index=True,
    )

    decided_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    agent_action: Mapped[AgentAction] = relationship(
        back_populates="approvals",
    )

    requester: Mapped[User] = relationship(
        foreign_keys=[requested_by],
        back_populates="requested_approvals",
    )

    approver: Mapped[User | None] = relationship(
        foreign_keys=[approved_by],
        back_populates="approved_approvals",
    )

    # ------------------------------------------------------------------
    # Indexes
    # ------------------------------------------------------------------

    __table_args__ = (
        Index(
            "ix_approvals_action_status",
            "agent_action_id",
            "status",
        ),
        Index(
            "ix_approvals_expires_status",
            "expires_at",
            "status",
        ),
    )

    # ------------------------------------------------------------------
    # DTO conversion
    # ------------------------------------------------------------------

    @classmethod
    def from_dto(
        cls,
        *,
        approval: ApprovalRequestDTO,
    ) -> Approval:
        """
        Create an Approval entity from an approval request DTO.

        Persistence-generated fields such as the approval ID and
        creation timestamp are intentionally not supplied here.
        """

        return cls(
            agent_action_id=approval.agent_action_id,
            requested_by=approval.requested_by,
            expires_at=approval.expires_at,
            status=approval.status,
        )

    def to_dto(self) -> ApprovalResponseDTO:
        """
        Convert the persisted Approval entity into a response DTO.
        """

        return ApprovalResponseDTO(
            approval_id=self.id,
            agent_action_id=self.agent_action_id,
            requested_by=self.requested_by,
            approved_by=self.approved_by,
            status=self.status,
            decision_type=self.decision_type,
            decision_reason=self.decision_reason,
            edited_payload=self.edited_payload,
            edited_fingerprint=self.edited_fingerprint,
            expires_at=self.expires_at,
            created_at=self.created_at,
            decided_at=self.decided_at,
        )

    @property
    def is_expired(self) -> bool:
        """
        Return whether the approval request has expired.
        """

        return datetime.now(UTC) >= self.expires_at
