"""
Unit tests for action workflow API dependencies.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.action_workflow import get_action_workflow_service
from src.authorization.approval_lifecycle.policy import ApprovalLifecyclePolicy
from src.authorization.service import AuthorizationService
from src.services.action_workflow import ActionWorkflowService
from src.services.agent_action import AgentActionService
from src.services.approval_lifecycle import ApprovalLifecycleService


def test_get_action_workflow_service_returns_service() -> None:
    """
    It should create an ActionWorkflowService.
    """

    session = MagicMock(
        spec=AsyncSession,
    )
    authorization_service = MagicMock(
        spec=AuthorizationService,
    )
    agent_action_service = MagicMock(
        spec=AgentActionService,
    )
    approval_lifecycle_service = MagicMock(
        spec=ApprovalLifecycleService,
    )

    result = get_action_workflow_service(
        session=session,
        authorization_service=authorization_service,
        agent_action_service=agent_action_service,
        approval_lifecycle_service=approval_lifecycle_service,
    )

    assert isinstance(
        result,
        ActionWorkflowService,
    )


def test_get_action_workflow_service_wires_dependencies() -> None:
    """
    It should wire all request-scoped dependencies into the workflow service.
    """

    session = MagicMock(
        spec=AsyncSession,
    )
    authorization_service = MagicMock(
        spec=AuthorizationService,
    )
    agent_action_service = MagicMock(
        spec=AgentActionService,
    )
    approval_lifecycle_service = MagicMock(
        spec=ApprovalLifecycleService,
    )

    result = get_action_workflow_service(
        session=session,
        authorization_service=authorization_service,
        agent_action_service=agent_action_service,
        approval_lifecycle_service=approval_lifecycle_service,
    )

    assert result._session is session
    assert result._agent_action_service is agent_action_service
    assert result._authorization_service is authorization_service
    assert result._approval_lifecycle_service is approval_lifecycle_service
    assert isinstance(
        result._approval_lifecycle_policy,
        ApprovalLifecyclePolicy,
    )


def test_get_action_workflow_service_creates_fresh_policy() -> None:
    """
    It should create a new approval lifecycle policy for each service instance.
    """

    session = MagicMock(
        spec=AsyncSession,
    )
    authorization_service = MagicMock(
        spec=AuthorizationService,
    )
    agent_action_service = MagicMock(
        spec=AgentActionService,
    )
    approval_lifecycle_service = MagicMock(
        spec=ApprovalLifecycleService,
    )

    first = get_action_workflow_service(
        session=session,
        authorization_service=authorization_service,
        agent_action_service=agent_action_service,
        approval_lifecycle_service=approval_lifecycle_service,
    )

    second = get_action_workflow_service(
        session=session,
        authorization_service=authorization_service,
        agent_action_service=agent_action_service,
        approval_lifecycle_service=approval_lifecycle_service,
    )

    assert first._approval_lifecycle_policy is not second._approval_lifecycle_policy


def test_get_action_workflow_service_does_not_replace_dependencies() -> None:
    """
    It should preserve the exact dependency instances supplied by FastAPI.
    """

    session = MagicMock(
        spec=AsyncSession,
    )
    authorization_service = MagicMock(
        spec=AuthorizationService,
    )
    agent_action_service = MagicMock(
        spec=AgentActionService,
    )
    approval_lifecycle_service = MagicMock(
        spec=ApprovalLifecycleService,
    )

    result = get_action_workflow_service(
        session=session,
        authorization_service=authorization_service,
        agent_action_service=agent_action_service,
        approval_lifecycle_service=approval_lifecycle_service,
    )

    assert result._session is session
    assert result._authorization_service is authorization_service
    assert result._agent_action_service is agent_action_service
    assert result._approval_lifecycle_service is approval_lifecycle_service
