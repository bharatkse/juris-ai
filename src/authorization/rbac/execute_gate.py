"""
Execute-time RBAC authorization gate.
"""

from __future__ import annotations

from src.authorization.rbac.protocols import RBACResolver
from src.core.dto.authorization import AuthorizationRequestDTO
from src.core.exceptions.authorization import AuthorizationError


class RBACExecuteGate:
    """
    Enforces RBAC immediately before action execution.

    The gate delegates the authorization decision to RBACService.
    It contains no permission rules of its own.
    """

    def __init__(
        self,
        rbac: RBACResolver,
    ) -> None:
        self._rbac = rbac

    def authorize(
        self,
        request: AuthorizationRequestDTO,
    ) -> None:
        """
        Authorize a concrete action before execution.
        """

        if not self._rbac.check_action(request):
            raise AuthorizationError(
                "Action is not authorized.",
            )
