"""
Action workflow service dependencies.
"""

from __future__ import annotations

from fastapi import Depends

from src.api.dependencies.action import get_action_service
from src.authorization.service import AuthorizationService
from src.runtime.factories.authorization import create_authorization
from src.services.action import ActionService
from src.services.action_workflow import ActionWorkflowService


def get_action_workflow_service(
    action_service: ActionService = Depends(
        get_action_service,
    ),
    authorization_service: AuthorizationService = Depends(
        create_authorization,
    ),
) -> ActionWorkflowService:
    """
    Create an ActionWorkflowService.
    """

    return ActionWorkflowService(
        action_service=action_service,
        authorization_service=authorization_service,
    )
