"""
Action workflow API dependencies.
"""

from __future__ import annotations

from fastapi import Depends

from src.api.dependencies.agent_action import get_agent_action_service
from src.api.dependencies.approval import get_approval_lifecycle_service
from src.api.dependencies.authorization import get_authorization_service
from src.authorization.approval_lifecycle.policy import ApprovalLifecyclePolicy
from src.authorization.service import AuthorizationService
from src.services.action_workflow import ActionWorkflowService
from src.services.agent_action import AgentActionService
from src.services.approval_lifecycle import ApprovalLifecycleService


def get_action_workflow_service(
    *,
    authorization_service: AuthorizationService = Depends(
        get_authorization_service,
    ),
    agent_action_service: AgentActionService = Depends(
        get_agent_action_service,
    ),
    approval_lifecycle_service: ApprovalLifecycleService = Depends(
        get_approval_lifecycle_service,
    ),
) -> ActionWorkflowService:
    """
    Create the request-scoped action workflow service.

    The workflow coordinates:
    - AgentAction persistence,
    - concrete action authorization,
    - HITL policy evaluation,
    - approval lifecycle creation.

    Request-scoped dependencies are resolved by FastAPI.
    """

    return ActionWorkflowService(
        agent_action_service=agent_action_service,
        authorization_service=authorization_service,
        approval_lifecycle_policy=ApprovalLifecyclePolicy(),
        approval_lifecycle_service=approval_lifecycle_service,
    )
