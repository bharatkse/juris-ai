"""
RBAC permission resolution.
"""

from __future__ import annotations

from src.authorization.rbac.policy import RBACPolicy
from src.authorization.rbac.protocols import RBACResolver
from src.core.dto.authorization import (
    ApplicationAuthorizationRequestDTO,
    AuthorizationRequestDTO,
)


class RBACService(RBACResolver):
    """
    Resolves RBAC permissions for capabilities and concrete actions.

    All permission decisions are delegated to the shared
    RBAC policy.
    """

    def __init__(
        self,
        policy: RBACPolicy,
    ) -> None:
        self._policy = policy

    def check_intent(
        self,
        request: ApplicationAuthorizationRequestDTO,
    ) -> bool:
        """
        Check requested capabilities before planning.
        """

        return all(
            self._policy.capability_allowed(
                user_id=request.user_id,
                capability=capability,
            )
            for capability in request.capabilities
        )

    def check_action(
        self,
        request: AuthorizationRequestDTO,
    ) -> bool:
        """
        Check user and agent permissions for a concrete action.
        """

        if not self._policy.user_action_allowed(
            user_id=request.user_id,
            action=request.action,
        ):
            return False

        return self._policy.agent_action_allowed(
            agent_id=request.agent_id,
            tool_name=request.tool_name,
            action=request.action,
        )
