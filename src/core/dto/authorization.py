"""
Authorization-related data transfer objects.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.enums import ActionTypeEnum, AuthorizationDecisionEnum


@dataclass(frozen=True, slots=True)
class AuthorizationRequestDTO:
    """
    Represents an authorization request for an actor attempting
    to perform an action through a specific tool against an
    optional resource.
    """

    user_id: str
    agent_id: str
    tool_name: str
    action: ActionTypeEnum
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
        return self.decision == AuthorizationDecisionEnum.ALLOW


@dataclass(frozen=True, slots=True)
class ApplicationAuthorizationRequestDTO:
    """
    Represents a user's requested application capabilities
    before an execution plan is created.
    """

    user_id: str
    capabilities: tuple[ActionTypeEnum, ...]
