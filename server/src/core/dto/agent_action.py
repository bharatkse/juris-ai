"""
Agent action data transfer objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.dto.authorization import AuthorizationRequestDTO
from core.enums import ActionTypeEnum, ActorTypeEnum, AgentActionStatusEnum


@dataclass(frozen=True, slots=True)
class AgentActionRequestDTO:
    """
    Represents a concrete executable action proposed by an agent
    during execution.

    This DTO describes the concrete action the agent has reasoned
    should be performed.

    It does not:
    - authorize the action,
    - grant human approval,
    - execute the action,
    - persist the action.

    The ActionWorkflowService is responsible for processing this
    proposed action through persistence, authorization, and approval
    policy.
    """

    execution_id: str
    thread_id: str
    conversation_event_id: str

    agent_id: str
    action_type: ActionTypeEnum

    actor_type: ActorTypeEnum = ActorTypeEnum.USER

    tool_name: str | None = None
    target_agent_id: str | None = None

    resource_type: str | None = None
    resource_id: str | None = None

    parameters: dict[str, Any] = field(
        default_factory=dict,
    )

    reason: str = ""

    def to_authorization_request(
        self,
        *,
        user_id: str,
    ) -> AuthorizationRequestDTO:
        """
        Convert this concrete action into an authorization request.

        Authorization is evaluated from the concrete action rather
        than from the agent's reasoning or original user message.
        """

        return AuthorizationRequestDTO(
            user_id=user_id,
            agent_id=self.agent_id,
            tool_name=self.tool_name,
            action_type=self.action_type,
            resource_id=self.resource_id,
        )

    @property
    def is_agent_call(self) -> bool:
        """
        Return whether this action targets another agent.
        """

        return self.action_type == ActionTypeEnum.AGENT_CALL or self.target_agent_id is not None

    @property
    def is_tool_action(self) -> bool:
        """
        Return whether this action targets a tool.
        """

        return self.tool_name is not None and not self.is_agent_call


@dataclass(frozen=True, slots=True)
class AgentActionResponseDTO:
    """
    Represents a persisted executable agent action.

    This DTO contains the persisted action state required by:
    - authorization,
    - approval,
    - execution,
    - audit,
    - resume flows.
    """

    action_id: str

    execution_id: str
    thread_id: str
    conversation_event_id: str

    agent_id: str
    action_type: ActionTypeEnum
    actor_type: ActorTypeEnum

    tool_name: str | None
    target_agent_id: str | None

    resource_type: str | None
    resource_id: str | None

    parameters: dict[str, Any]

    reason: str

    status: AgentActionStatusEnum

    fingerprint: str

    def to_authorization_request(
        self,
        *,
        user_id: str,
    ) -> AuthorizationRequestDTO:
        """
        Convert the persisted concrete action into an
        authorization request.

        This is only a DTO transformation.

        Authorization itself remains owned by the
        authorization layer.
        """

        return AuthorizationRequestDTO(
            user_id=user_id,
            agent_id=self.agent_id,
            tool_name=self.tool_name,
            action_type=self.action_type,
            resource_id=self.resource_id,
        )

    @property
    def is_agent_call(self) -> bool:
        """
        Return whether this action targets another agent.
        """

        return self.action_type == ActionTypeEnum.AGENT_CALL or self.target_agent_id is not None

    @property
    def is_tool_action(self) -> bool:
        """
        Return whether this action targets a tool.
        """

        return self.tool_name is not None and not self.is_agent_call

    @property
    def is_pending_approval(self) -> bool:
        """
        Return whether this action is waiting for human approval.
        """

        return self.status == AgentActionStatusEnum.PENDING_APPROVAL

    @property
    def is_approved(self) -> bool:
        """
        Return whether this action has been approved.
        """

        return self.status == AgentActionStatusEnum.APPROVED

    @property
    def is_terminal(self) -> bool:
        """
        Return whether the action has reached a terminal state.
        """

        return self.status in {
            AgentActionStatusEnum.COMPLETED,
            AgentActionStatusEnum.FAILED,
            AgentActionStatusEnum.REJECTED,
            AgentActionStatusEnum.EXPIRED,
        }
