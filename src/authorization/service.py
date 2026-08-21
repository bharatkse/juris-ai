"""
Authorization facade.

Provides the application-facing authorization boundary for
request-level and action-level authorization.
"""

from __future__ import annotations

from src.authorization.approval_lifecycle.fingerprint import create_action_fingerprint
from src.authorization.approval_lifecycle.policy import ApprovalLifecyclePolicy
from src.authorization.approval_lifecycle.protocols import ApprovalLifecycle
from src.authorization.capability.protocols import CapabilityAnalyzer
from src.authorization.rbac.execute_gate import RBACExecuteGate
from src.authorization.rbac.resolver import RBACService
from src.core.dto.action import ActionResponseDTO
from src.core.dto.approval import ApprovalResponseDTO
from src.core.dto.authorization import ApplicationAuthorizationRequestDTO
from src.core.dto.capability import CapabilityAnalysisDTO
from src.core.exceptions.authorization import AuthorizationError


class AuthorizationService:
    """
    Application-facing authorization facade.

    Coordinates capability analysis, RBAC, and human approval.
    Individual authorization responsibilities remain delegated
    to their respective components.
    """

    def __init__(
        self,
        *,
        capability_analyzer: CapabilityAnalyzer,
        rbac: RBACService,
        approval_lifecycle_policy: ApprovalLifecyclePolicy,
        approval_lifecycle_service: ApprovalLifecycle,
        execute_gate: RBACExecuteGate,
    ) -> None:
        self._capability_analyzer = capability_analyzer
        self._rbac = rbac
        self._approval_lifecycle_policy = approval_lifecycle_policy
        self._approval_lifecycle_service = approval_lifecycle_service
        self._execute_gate = execute_gate

    def authorize_request(
        self,
        user_id: str,
        message: str,
    ) -> CapabilityAnalysisDTO:
        """
        Authorize the user's requested capabilities before planning.
        """

        analysis = self._capability_analyzer.analyze(
            message,
        )

        request = ApplicationAuthorizationRequestDTO(
            user_id=user_id,
            capabilities=analysis.actions,
        )

        if not self._rbac.check_intent(request):
            raise AuthorizationError(
                "User is not authorized for the requested capabilities.",
            )

        return analysis

    async def prepare_approval_request_action(
        self,
        *,
        user_id: str,
        action: ActionResponseDTO,
    ) -> ApprovalResponseDTO | None:
        """
        Prepare a persisted action for the approval workflow.

        If the action requires human approval, create and persist
        a durable approval request.

        If approval is not required, perform the final RBAC
        authorization and return None.

        This method never waits for human approval.
        """

        approval_result = self._approval_lifecycle_policy.evaluate(
            action,
        )

        if approval_result.requires_approval:
            return await self._approval_lifecycle_service.create(
                action=action,
                requested_by=user_id,
            )

        self._authorize_with_rbac(
            user_id=user_id,
            action=action,
        )

        return None

    async def authorize_approved_action(
        self,
        *,
        user_id: str,
        approval_id: str,
        action: ActionResponseDTO,
    ) -> None:
        """
        Authorize a concrete action after human approval.

        The approval must:
            - exist,
            - still be valid,
            - be approved,
            - correspond exactly to the action being executed.

        Final RBAC authorization is performed again before execution.
        """

        approval = await self._approval_lifecycle_service.validate(
            approval_id,
        )

        if approval.action_id != action.action_id:
            raise AuthorizationError(
                "Approved action does not match the requested action.",
            )

        action_fingerprint = create_action_fingerprint(
            action,
        )

        if approval.action_fingerprint != action_fingerprint:
            raise AuthorizationError(
                "Approved action does not match the requested action.",
            )

        self._authorize_with_rbac(
            user_id=user_id,
            action=action,
        )

    def _authorize_with_rbac(
        self,
        *,
        user_id: str,
        action: ActionResponseDTO,
    ) -> None:
        """
        Perform final RBAC authorization for a persisted action.
        """

        request = action.to_authorization_request(
            user_id=user_id,
        )

        self._execute_gate.authorize(
            request,
        )

    async def get_approval(
        self,
        approval_id: str,
    ) -> ApprovalResponseDTO:
        """
        Retrieve a human approval request.
        """

        return await self._approval_lifecycle_service.get(
            approval_id,
        )
