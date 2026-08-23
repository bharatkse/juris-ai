"""
Agent action database model.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON as JSONB
from sqlalchemy import Enum as PgEnum
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.dto.agent_action import AgentActionRequestDTO, AgentActionResponseDTO
from src.core.enums import ActionTypeEnum, ActorTypeEnum, AgentActionStatusEnum
from src.db.base import Base
from src.db.mixins import PrimaryKeyMixin, TimestampMixin

if TYPE_CHECKING:
    from .approval import Approval
    from .conversation_event import ConversationEvent
    from .user import User


class AgentAction(
    Base,
    PrimaryKeyMixin,
    TimestampMixin,
):
    """
    Persisted concrete action proposed during execution.

    An AgentAction represents one executable unit produced by
    an agent/executor workflow.

    It may target:

    - a tool,
    - a resource,
    - another agent,
    - or another execution capability.

    This model does not own authorization or approval policy.
    Those concerns belong to their respective application/domain
    services.
    """

    __tablename__ = "agent_actions"
    _id_prefix = "actn"

    # ------------------------------------------------------------------
    # Execution / traceability
    # ------------------------------------------------------------------

    conversation_event_id: Mapped[str] = mapped_column(
        ForeignKey("conversation_events.id"),
        nullable=False,
        index=True,
    )

    execution_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    thread_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------
    # Accountability / tenancy
    # ------------------------------------------------------------------

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    tenant_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------
    # Actor
    # ------------------------------------------------------------------

    actor_type: Mapped[ActorTypeEnum] = mapped_column(
        PgEnum(
            ActorTypeEnum,
            name="actor_type",
        ),
        nullable=False,
        default=ActorTypeEnum.USER,
    )

    agent_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------
    # Action target
    # ------------------------------------------------------------------

    action_type: Mapped[ActionTypeEnum] = mapped_column(
        PgEnum(
            ActionTypeEnum,
            name="action_type",
        ),
        nullable=False,
        index=True,
    )

    tool_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    target_agent_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )

    resource_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    resource_id: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        index=True,
    )

    # ------------------------------------------------------------------
    # Action payload
    # ------------------------------------------------------------------

    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )

    # ------------------------------------------------------------------
    # Action lifecycle
    # ------------------------------------------------------------------

    status: Mapped[AgentActionStatusEnum] = mapped_column(
        PgEnum(
            AgentActionStatusEnum,
            name="agent_action_status",
        ),
        nullable=False,
        default=AgentActionStatusEnum.DRAFT,
        index=True,
    )

    # ------------------------------------------------------------------
    # Action integrity
    # ------------------------------------------------------------------

    fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------
    # Execution result
    # ------------------------------------------------------------------

    result: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    executed_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    event: Mapped[ConversationEvent] = relationship(
        back_populates="agent_actions",
    )

    user: Mapped[User] = relationship(
        back_populates="agent_actions",
    )

    approvals: Mapped[list[Approval]] = relationship(
        back_populates="agent_action",
        cascade="all, delete-orphan",
    )

    # ------------------------------------------------------------------
    # Composite indexes
    # ------------------------------------------------------------------

    __table_args__ = (
        Index(
            "ix_agent_actions_execution_status",
            "execution_id",
            "status",
        ),
        Index(
            "ix_agent_actions_thread_status",
            "thread_id",
            "status",
        ),
    )

    # ------------------------------------------------------------------
    # DTO mapping
    # ------------------------------------------------------------------

    @classmethod
    def from_dto(
        cls,
        *,
        action: AgentActionRequestDTO,
        user_id: str,
        tenant_id: str,
        fingerprint: str,
    ) -> AgentAction:
        """
        Build a persistence entity from an action DTO.

        Repository code should not construct AgentAction directly.
        Entity construction belongs to the model mapping boundary.
        """

        return cls(
            execution_id=action.execution_id,
            thread_id=action.thread_id,
            conversation_event_id=action.conversation_event_id,
            user_id=user_id,
            tenant_id=tenant_id,
            actor_type=action.actor_type,
            agent_id=action.agent_id,
            action_type=action.action_type,
            tool_name=action.tool_name,
            target_agent_id=action.target_agent_id,
            resource_type=action.resource_type,
            resource_id=action.resource_id,
            parameters=action.parameters,
            reason=action.reason,
            status=AgentActionStatusEnum.DRAFT,
            fingerprint=fingerprint,
        )

    def to_dto(self) -> AgentActionResponseDTO:
        """
        Convert the persisted entity into an action response DTO.
        """

        return AgentActionResponseDTO(
            action_id=self.id,
            execution_id=self.execution_id,
            thread_id=self.thread_id,
            conversation_event_id=self.conversation_event_id,
            agent_id=self.agent_id,
            action_type=self.action_type,
            actor_type=self.actor_type,
            tool_name=self.tool_name,
            target_agent_id=self.target_agent_id,
            resource_type=self.resource_type,
            resource_id=self.resource_id,
            parameters=dict(self.parameters),
            reason=self.reason,
            status=self.status,
            fingerprint=self.fingerprint,
        )
