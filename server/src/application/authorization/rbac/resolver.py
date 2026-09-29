"""
RBAC permission resolution.
"""

from __future__ import annotations

from application.authorization.rbac.policy import RBACPolicy
from application.authorization.rbac.protocols import RBACResolverProtocol
from application.authorization.rbac.roles import RolePermissionProvider
from core.dto.authorization import (
    ApplicationAuthorizationRequestDTO,
    AuthorizationRequestDTO,
)


class RBACService(RBACResolverProtocol):
    """
    Resolves RBAC permissions for application requests
    and concrete actions.

    A user's permissions come from their role in the database
    (RolePermissionProvider); an agent's from RBACPolicy.

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
        role_permissions: RolePermissionProvider,
    ) -> None:
        self._policy = policy
        self._role_permissions = role_permissions

    async def check_intent(
        self,
        request: ApplicationAuthorizationRequestDTO,
    ) -> bool:
        """
        Check whether the user may request all identified
        capabilities before planning.
        """

        if not request.capabilities:
            return True

        granted = await self._role_permissions.permissions_for(
            user_id=request.user_id,
        )

        return all(capability in granted for capability in request.capabilities)

    async def check_action(
        self,
        request: AuthorizationRequestDTO,
    ) -> bool:
        """
        Check whether the concrete action is authorized.

        Both the requesting user and the executing agent/tool
        must have permission for the requested action.
        """

        granted = await self._role_permissions.permissions_for(
            user_id=request.user_id,
        )

        if request.action_type not in granted:
            return False

        return self._policy.agent_action_allowed(
            agent_id=request.agent_id,
            tool_name=request.tool_name,
            action=request.action_type,
        )
