"""
Authorization-related data transfer objects.

Authorization determines whether a concrete AgentAction is permitted.
It does not perform human approval or action execution.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.enums import ActionTypeEnum, AuthorizationDecisionEnum


@dataclass(frozen=True, slots=True)
class AuthorizationRequestDTO:
    """
    Represents a request to authorize a concrete action.

    The request contains the identity and action attributes required
    by the authorization layer.

    Authorization does not determine whether human approval is required.
    """

    user_id: str
    agent_id: str
    action_type: ActionTypeEnum

    tool_name: str | None = None
    resource_id: str | None = None


@dataclass(frozen=True, slots=True)
class AuthorizationResultDTO:
    """
    Result of an authorization evaluation.
    """

    decision: AuthorizationDecisionEnum
    reason: str

    @property
    def is_allowed(self) -> bool:
        """
        Return whether the action is authorized.
        """

        return self.decision == AuthorizationDecisionEnum.ALLOW

    @property
    def is_denied(self) -> bool:
        """
        Return whether the action is denied.
        """

        return self.decision == AuthorizationDecisionEnum.DENY


@dataclass(frozen=True, slots=True)
class ApplicationAuthorizationRequestDTO:
    """
    Represents the capabilities identified from a user's request
    before execution planning.

    This is used at the application/request boundary.

    It does not represent authorization of a concrete executable
    AgentAction.
    """

    user_id: str
    capabilities: tuple[ActionTypeEnum, ...]
