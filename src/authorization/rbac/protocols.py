"""
RBAC protocols.
"""

from __future__ import annotations

from typing import Protocol

from src.core.dto.authorization import (
    ApplicationAuthorizationRequestDTO,
    AuthorizationRequestDTO,
)


class RBACResolver(Protocol):
    """
    Contract for RBAC authorization.
    """

    def check_intent(
        self,
        request: ApplicationAuthorizationRequestDTO,
    ) -> bool:
        """
        Check user capability permissions before planning.
        """

        ...

    def check_action(
        self,
        request: AuthorizationRequestDTO,
    ) -> bool:
        """
        Check user and agent permissions before execution.
        """

        ...
