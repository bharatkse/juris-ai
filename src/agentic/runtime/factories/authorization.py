"""
Runtime authorization composition.

Creates the complete authorization subsystem.

No authorization business logic belongs in this module.
"""

from __future__ import annotations

from application.authorization.capability.analyzer import DefaultCapabilityAnalyzer
from application.authorization.rbac.execute_gate import RBACExecuteGate
from application.authorization.rbac.policy import RBACPolicy
from application.authorization.rbac.resolver import RBACService
from application.authorization.service import AuthorizationService


def create_authorization() -> AuthorizationService:
    """
    Create the application authorization service.
    """

    capability_analyzer = DefaultCapabilityAnalyzer()
    rbac_policy = RBACPolicy.default()

    rbac = RBACService(
        policy=rbac_policy,
    )

    execute_gate = RBACExecuteGate(
        rbac=rbac,
    )

    return AuthorizationService(
        capability_analyzer=capability_analyzer,
        rbac=rbac,
        execute_gate=execute_gate,
    )
