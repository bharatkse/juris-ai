"""
RBAC protocols.
"""

from __future__ import annotations

from typing import Protocol

from core.dto.authorization import (
    ApplicationAuthorizationRequestDTO,
    AuthorizationRequestDTO,
)


class RBACResolverProtocol(Protocol):
    """
    Contract for RBAC authorization.

    Implementations resolve:
    - application/request-level capability authorization,
    - concrete action authorization.

    The protocol does not define:
    - capability classification,
    - approval policy,
    - approval lifecycle,
    - action execution.
    """

    def check_intent(
        self,
        request: ApplicationAuthorizationRequestDTO,
    ) -> bool:
        """
        Check whether the requester may request the
        identified capabilities before planning.
        """

        ...

    def check_action(
        self,
        request: AuthorizationRequestDTO,
    ) -> bool:
        """
        Check whether a concrete action is authorized
        before execution.
        """

        ...
