"""
Action workflow API dependencies.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.session import get_db_session
from api.dependencies.agent_action import get_agent_action_service
from api.dependencies.approval import get_approval_lifecycle_service
from api.dependencies.authorization import get_authorization_service
from application.authorization.approval_lifecycle.policy import ApprovalLifecyclePolicy
from application.authorization.service import AuthorizationService
from application.services.action_workflow import ActionWorkflowService
from application.services.agent_action import AgentActionService
from application.services.approval_lifecycle import ApprovalLifecycleService


def get_action_workflow_service(
    *,
    session: AsyncSession = Depends(
        get_db_session,
    ),
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
        session=session,
        agent_action_service=agent_action_service,
        authorization_service=authorization_service,
        approval_lifecycle_policy=ApprovalLifecyclePolicy(),
        approval_lifecycle_service=approval_lifecycle_service,
    )
