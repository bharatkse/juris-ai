"""
Agent action workflow service.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from application.authorization.approval_lifecycle.policy import ApprovalLifecyclePolicy
from application.authorization.service import AuthorizationService
from application.services.agent_action import AgentActionService
from application.services.approval_lifecycle import ApprovalLifecycleService
from application.services.base import BaseService
from core.dto.action_workflow import ActionWorkflowResultDTO
from core.dto.agent_action import AgentActionRequestDTO
from core.exceptions.authorization import AuthorizationError


class ActionWorkflowService(BaseService):
    """
    Coordinates preparation of a concrete AgentAction.

    Responsibilities:
    - Persist the concrete AgentAction.
    - Perform concrete action authorization.
    - Evaluate the HITL approval policy.
    - Create a durable approval request when required.
    - Return immediately without waiting for approval.

    It does not:
    - implement RBAC rules,
    - implement approval policy rules,
    - implement approval lifecycle rules,
    - execute actions,
    - wait for human approval.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        agent_action_service: AgentActionService,
        authorization_service: AuthorizationService,
        approval_lifecycle_policy: ApprovalLifecyclePolicy,
        approval_lifecycle_service: ApprovalLifecycleService,
    ) -> None:
        super().__init__(session)
        self._agent_action_service = agent_action_service
        self._authorization_service = authorization_service
        self._approval_lifecycle_policy = approval_lifecycle_policy
        self._approval_lifecycle_service = approval_lifecycle_service

    async def prepare(
        self,
        *,
        user_id: str,
        tenant_id: str,
        action: AgentActionRequestDTO,
    ) -> ActionWorkflowResultDTO:
        """
        Prepare a concrete AgentAction for execution.

        Workflow:

        1. Persist the concrete AgentAction.
        2. Authorize the persisted concrete action.
        3. Evaluate the HITL approval policy.
        4. Create a durable approval request when required.
        5. Return immediately.

        Human approval is handled separately and never blocks
        this workflow.
        """

        # ---------------------------------------------------------
        # 1. Persist concrete AgentAction
        # ---------------------------------------------------------

        persisted_action = await self._agent_action_service.create(
            action=action,
            user_id=user_id,
            tenant_id=tenant_id,
        )

        action_dto = persisted_action.to_dto()

        # ---------------------------------------------------------
        # 2. Authorize concrete action
        # ---------------------------------------------------------

        authorization_result = self._authorization_service.authorize_action(
            user_id=user_id,
            action=action_dto,
        )

        if not authorization_result.is_allowed:
            raise AuthorizationError(
                authorization_result.reason,
            )

        # ---------------------------------------------------------
        # 3. Evaluate HITL policy
        # ---------------------------------------------------------

        policy_result = self._approval_lifecycle_policy.evaluate(
            action_dto,
        )

        # ---------------------------------------------------------
        # 4. No approval required
        # ---------------------------------------------------------

        if not policy_result.requires_approval:
            return ActionWorkflowResultDTO(
                action=action_dto,
            )

        # ---------------------------------------------------------
        # 5. Approval required
        # ---------------------------------------------------------

        approval = await self._approval_lifecycle_service.create(
            action=action_dto,
            requested_by=user_id,
        )

        return ActionWorkflowResultDTO(
            action=action_dto,
            approval=approval,
        )
