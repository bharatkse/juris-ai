"""
RBAC permission resolution.
"""

from __future__ import annotations

from application.authorization.rbac.policy import RBACPolicy
from application.authorization.rbac.protocols import RBACResolverProtocol
from core.dto.authorization import (
    ApplicationAuthorizationRequestDTO,
    AuthorizationRequestDTO,
)


class RBACService(RBACResolverProtocol):
    """
    Resolves RBAC permissions for application requests
    and concrete actions.

    All permission decisions are delegated to RBACPolicy.

    This service does not:
    - analyze capabilities,
    - evaluate approval requirements,
    - create approvals,
    - execute actions.
    """

    def __init__(
        self,
        *,
        policy: RBACPolicy,
    ) -> None:
        self._policy = policy

    def check_intent(
        self,
        request: ApplicationAuthorizationRequestDTO,
    ) -> bool:
        """
        Check whether the user may request all identified
        capabilities before planning.
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
        Check whether the concrete action is authorized.

        Both the requesting user and the executing agent/tool
        must have permission for the requested action.
        """

        if not self._policy.user_action_allowed(
            user_id=request.user_id,
            action=request.action_type,
        ):
            return False

        return self._policy.agent_action_allowed(
            agent_id=request.agent_id,
            tool_name=request.tool_name,
            action=request.action_type,
        )
