"""
Action workflow service.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.authorization.service import AuthorizationService
from src.core.dto.action import ActionRequestDTO, ActionResponseDTO
from src.core.dto.approval import ApprovalResponseDTO
from src.services.action import ActionService


@dataclass(frozen=True, slots=True)
class ActionWorkflowResultDTO:
    """
    Result of authorizing a concrete action.
    """

    action: ActionResponseDTO

    approval: ApprovalResponseDTO | None = None

    @property
    def approval_required(self) -> bool:
        """
        Return whether human approval is required.
        """

        return self.approval is not None


class ActionWorkflowService:
    """
    Coordinates the action authorization workflow.

    Responsibilities:
    - Persist the concrete action.
    - Verify authorization for the action.
    - Create an approval request when policy requires it.

    It does not:
    - execute the action,
    - own RBAC rules,
    - own approval lifecycle rules,
    - decide how agents communicate.

    The same workflow can be used for user-originated and
    agent-originated actions.
    """

    def __init__(
        self,
        *,
        action_service: ActionService,
        authorization_service: AuthorizationService,
    ) -> None:
        self._action_service = action_service
        self._authorization_service = authorization_service

    async def authorize(
        self,
        *,
        event_id: str,
        user_id: str,
        action: ActionRequestDTO,
    ) -> ActionWorkflowResultDTO:
        """
        Persist and authorize a concrete action.

        Depending on authorization policy, the result may contain
        a human approval request.

        When approval is not required, the returned approval is
        None and the caller may continue with execution.
        """

        persisted_action = await self._action_service.create(
            event_id=event_id,
            action=action,
        )

        approval = await self._authorization_service.prepare_approval_request_action(
            user_id=user_id,
            action=persisted_action,
        )

        return ActionWorkflowResultDTO(
            action=persisted_action,
            approval=approval,
        )
