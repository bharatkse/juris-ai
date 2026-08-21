"""
Action-related data transfer objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.core.dto.authorization import AuthorizationRequestDTO
from src.core.enums import ActionTypeEnum


@dataclass(frozen=True, slots=True)
class ActionRequestDTO:
    """
    Represents a concrete executable action requested during execution.

    This object describes what the Executor is about to perform.
    It does not grant authorization or approval.
    """

    action_type: ActionTypeEnum

    agent_id: str

    tool_name: str | None = None

    target_agent_id: str | None = None

    arguments: dict[str, Any] = field(
        default_factory=dict,
    )

    reason: str = ""

    resource_id: str | None = None

    def to_authorization_request(
        self,
        user_id: str,
    ) -> AuthorizationRequestDTO:
        """
        Create an authorization request for this action.
        """

        return AuthorizationRequestDTO(
            user_id=user_id,
            agent_id=self.agent_id,
            tool_name=self.tool_name,
            action_type=self.action_type,
            resource_id=self.resource_id,
        )


@dataclass(frozen=True, slots=True)
class ActionResponseDTO:
    """
    Represents a persisted executable action.
    """

    action_id: str

    event_id: str

    action_type: ActionTypeEnum

    agent_id: str

    tool_name: str | None = None

    target_agent_id: str | None = None

    arguments: dict[str, Any] = field(
        default_factory=dict,
    )

    reason: str = ""

    resource_id: str | None = None
