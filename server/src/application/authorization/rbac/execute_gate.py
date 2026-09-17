"""
Execute-time RBAC authorization gate.
"""

from __future__ import annotations

from application.authorization.rbac.protocols import RBACResolverProtocol
from core.dto.authorization import AuthorizationRequestDTO, AuthorizationResultDTO
from core.enums import AuthorizationDecisionEnum


class RBACExecuteGate:
    """
    Enforces RBAC immediately before action execution.

    The gate delegates the authorization decision to RBACService.

    It does not:
    - define permission rules,
    - perform capability analysis,
    - evaluate approval policy,
    - create approvals,
    - execute actions.
    """

    def __init__(
        self,
        *,
        rbac: RBACResolverProtocol,
    ) -> None:
        self._rbac = rbac

    def authorize(
        self,
        request: AuthorizationRequestDTO,
    ) -> AuthorizationResultDTO:
        """
        Authorize a concrete action before execution.

        Returns the authorization decision produced by the
        RBAC resolver.
        """

        allowed = self._rbac.check_action(
            request,
        )

        if allowed:
            return AuthorizationResultDTO(
                decision=AuthorizationDecisionEnum.ALLOW,
                reason="Action is authorized.",
            )

        return AuthorizationResultDTO(
            decision=AuthorizationDecisionEnum.DENY,
            reason="Action is not authorized.",
        )
