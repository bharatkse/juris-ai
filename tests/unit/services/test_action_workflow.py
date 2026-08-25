"""
Unit tests for agent action workflow service.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.authorization.approval_lifecycle.policy import ApprovalLifecyclePolicy
from src.authorization.service import AuthorizationService
from src.core.dto.action_workflow import ActionWorkflowResultDTO
from src.core.dto.agent_action import AgentActionRequestDTO
from src.core.exceptions.authorization import AuthorizationError
from src.services.action_workflow import ActionWorkflowService
from src.services.agent_action import AgentActionService
from src.services.approval_lifecycle import ApprovalLifecycleService


def build_action_request() -> AgentActionRequestDTO:
    """
    Build a concrete agent action request for testing.
    """

    return AgentActionRequestDTO(
        execution_id="execution-123",
        thread_id="thread-123",
        conversation_event_id="event-123",
        agent_id="agent-123",
        action_type=MagicMock(),
        tool_name="send_email",
        resource_type="email",
        resource_id="email-123",
        parameters={
            "recipient": "user@example.com",
        },
        reason="Send the approved email.",
    )


def build_persisted_action(
    action_dto: object,
) -> MagicMock:
    """
    Build a persisted AgentAction mock.
    """

    persisted_action = MagicMock()

    persisted_action.to_dto.return_value = action_dto

    return persisted_action


def build_authorization_result(
    *,
    is_allowed: bool,
    reason: str = "",
) -> SimpleNamespace:
    """
    Build an authorization result.
    """

    return SimpleNamespace(
        is_allowed=is_allowed,
        reason=reason,
    )


def build_policy_result(
    *,
    requires_approval: bool,
) -> SimpleNamespace:
    """
    Build an approval policy result.
    """

    return SimpleNamespace(
        requires_approval=requires_approval,
    )


@pytest.fixture
def session() -> MagicMock:
    """
    Provide a mocked database session.
    """

    return MagicMock()


@pytest.fixture
def agent_action_service() -> MagicMock:
    """
    Provide a mocked AgentActionService.
    """

    service = MagicMock(
        spec=AgentActionService,
    )
    service.create = AsyncMock()

    return service


@pytest.fixture
def authorization_service() -> MagicMock:
    """
    Provide a mocked AuthorizationService.
    """

    return MagicMock(
        spec=AuthorizationService,
    )


@pytest.fixture
def approval_lifecycle_policy() -> MagicMock:
    """
    Provide a mocked approval lifecycle policy.
    """

    return MagicMock(
        spec=ApprovalLifecyclePolicy,
    )


@pytest.fixture
def approval_lifecycle_service() -> MagicMock:
    """
    Provide a mocked ApprovalLifecycleService.
    """

    service = MagicMock(
        spec=ApprovalLifecycleService,
    )
    service.create = AsyncMock()

    return service


@pytest.fixture
def workflow_service(
    session: MagicMock,
    agent_action_service: MagicMock,
    authorization_service: MagicMock,
    approval_lifecycle_policy: MagicMock,
    approval_lifecycle_service: MagicMock,
) -> ActionWorkflowService:
    """
    Create an ActionWorkflowService with mocked dependencies.
    """

    return ActionWorkflowService(
        session=session,
        agent_action_service=agent_action_service,
        authorization_service=authorization_service,
        approval_lifecycle_policy=approval_lifecycle_policy,
        approval_lifecycle_service=approval_lifecycle_service,
    )


@pytest.mark.asyncio
async def test_prepare_returns_action_when_approval_not_required(
    workflow_service: ActionWorkflowService,
    agent_action_service: MagicMock,
    authorization_service: MagicMock,
    approval_lifecycle_policy: MagicMock,
    approval_lifecycle_service: MagicMock,
) -> None:
    """
    It should return the persisted action when approval is not required.
    """

    action = build_action_request()

    action_dto = MagicMock()

    persisted_action = build_persisted_action(
        action_dto,
    )

    agent_action_service.create.return_value = persisted_action

    authorization_service.authorize_action.return_value = build_authorization_result(
        is_allowed=True,
    )

    approval_lifecycle_policy.evaluate.return_value = build_policy_result(
        requires_approval=False,
    )

    result = await workflow_service.prepare(
        user_id="user-123",
        tenant_id="tenant-123",
        action=action,
    )

    assert isinstance(
        result,
        ActionWorkflowResultDTO,
    )

    assert result.action is action_dto
    assert result.approval is None

    agent_action_service.create.assert_awaited_once_with(
        action=action,
        user_id="user-123",
        tenant_id="tenant-123",
    )

    persisted_action.to_dto.assert_called_once_with()

    authorization_service.authorize_action.assert_called_once_with(
        user_id="user-123",
        action=action_dto,
    )

    approval_lifecycle_policy.evaluate.assert_called_once_with(
        action_dto,
    )

    approval_lifecycle_service.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_creates_approval_when_required(
    workflow_service: ActionWorkflowService,
    agent_action_service: MagicMock,
    authorization_service: MagicMock,
    approval_lifecycle_policy: MagicMock,
    approval_lifecycle_service: MagicMock,
) -> None:
    """
    It should create a durable approval when policy requires it.
    """

    action = build_action_request()

    action_dto = MagicMock(
        name="action_dto",
    )

    approval = MagicMock(
        name="approval",
    )

    persisted_action = build_persisted_action(
        action_dto,
    )

    agent_action_service.create.return_value = persisted_action

    authorization_service.authorize_action.return_value = build_authorization_result(
        is_allowed=True,
    )

    approval_lifecycle_policy.evaluate.return_value = build_policy_result(
        requires_approval=True,
    )

    approval_lifecycle_service.create.return_value = approval

    result = await workflow_service.prepare(
        user_id="user-123",
        tenant_id="tenant-123",
        action=action,
    )

    assert isinstance(
        result,
        ActionWorkflowResultDTO,
    )

    assert result.action is action_dto
    assert result.approval is approval

    agent_action_service.create.assert_awaited_once_with(
        action=action,
        user_id="user-123",
        tenant_id="tenant-123",
    )

    authorization_service.authorize_action.assert_called_once_with(
        user_id="user-123",
        action=action_dto,
    )

    approval_lifecycle_policy.evaluate.assert_called_once_with(
        action_dto,
    )

    approval_lifecycle_service.create.assert_awaited_once_with(
        action=action_dto,
        requested_by="user-123",
    )


@pytest.mark.asyncio
async def test_prepare_raises_authorization_error_when_action_is_denied(
    workflow_service: ActionWorkflowService,
    agent_action_service: MagicMock,
    authorization_service: MagicMock,
    approval_lifecycle_policy: MagicMock,
    approval_lifecycle_service: MagicMock,
) -> None:
    """
    It should reject an action when authorization denies it.
    """

    action = build_action_request()

    action_dto = MagicMock()

    persisted_action = build_persisted_action(
        action_dto,
    )

    agent_action_service.create.return_value = persisted_action

    authorization_service.authorize_action.return_value = build_authorization_result(
        is_allowed=False,
        reason="User is not authorized to send email.",
    )

    with pytest.raises(
        AuthorizationError,
        match="User is not authorized to send email.",
    ):
        await workflow_service.prepare(
            user_id="user-123",
            tenant_id="tenant-123",
            action=action,
        )

    agent_action_service.create.assert_awaited_once_with(
        action=action,
        user_id="user-123",
        tenant_id="tenant-123",
    )

    persisted_action.to_dto.assert_called_once_with()

    authorization_service.authorize_action.assert_called_once_with(
        user_id="user-123",
        action=action_dto,
    )

    approval_lifecycle_policy.evaluate.assert_not_called()

    approval_lifecycle_service.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_does_not_create_approval_when_not_required(
    workflow_service: ActionWorkflowService,
    agent_action_service: MagicMock,
    authorization_service: MagicMock,
    approval_lifecycle_policy: MagicMock,
    approval_lifecycle_service: MagicMock,
) -> None:
    """
    It should not create an approval when policy allows immediate execution.
    """

    action = build_action_request()

    action_dto = MagicMock()

    agent_action_service.create.return_value = build_persisted_action(
        action_dto,
    )

    authorization_service.authorize_action.return_value = build_authorization_result(
        is_allowed=True,
    )

    approval_lifecycle_policy.evaluate.return_value = build_policy_result(
        requires_approval=False,
    )

    await workflow_service.prepare(
        user_id="user-123",
        tenant_id="tenant-123",
        action=action,
    )

    approval_lifecycle_service.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_prepare_uses_persisted_action_for_authorization(
    workflow_service: ActionWorkflowService,
    agent_action_service: MagicMock,
    authorization_service: MagicMock,
    approval_lifecycle_policy: MagicMock,
) -> None:
    """
    It should authorize the persisted concrete action rather than
    the original request DTO.
    """

    action = build_action_request()

    original_action_dto = MagicMock(
        name="original_action",
    )

    persisted_action_dto = MagicMock(
        name="persisted_action",
    )

    agent_action_service.create.return_value = build_persisted_action(
        persisted_action_dto,
    )

    authorization_service.authorize_action.return_value = build_authorization_result(
        is_allowed=True,
    )

    approval_lifecycle_policy.evaluate.return_value = build_policy_result(
        requires_approval=False,
    )

    await workflow_service.prepare(
        user_id="user-123",
        tenant_id="tenant-123",
        action=action,
    )

    authorization_service.authorize_action.assert_called_once_with(
        user_id="user-123",
        action=persisted_action_dto,
    )

    assert (
        authorization_service.authorize_action.call_args.kwargs["action"] is not original_action_dto
    )
