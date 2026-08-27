"""
Unit tests for agent action application service.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.persistence.sqlalchemy.models.agent_action import AgentAction
from adapters.persistence.sqlalchemy.repositories.agent_action import (
    AgentActionRepository,
)
from application.services.agent_action import AgentActionService
from core.dto.agent_action import AgentActionRequestDTO
from core.enums import ActionTypeEnum, ActorTypeEnum
from core.exceptions.agent_action import AgentActionError


def build_agent_action_request() -> AgentActionRequestDTO:
    """
    Build a valid agent action request.
    """

    return AgentActionRequestDTO(
        execution_id="execution-123",
        thread_id="thread-123",
        conversation_event_id="event-123",
        agent_id="agent-123",
        action_type=ActionTypeEnum.TOOL_CALL,
        actor_type=ActorTypeEnum.USER,
        tool_name="send_email",
        parameters={
            "recipient": "user@example.com",
        },
        reason="Send an email to the user.",
    )


@pytest.fixture
def mock_repository() -> MagicMock:
    """
    Provide a mocked AgentActionRepository.
    """

    repository = MagicMock(
        spec=AgentActionRepository,
    )

    repository.create = AsyncMock()

    return repository


@pytest.fixture
def mock_session() -> MagicMock:
    """
    Provide a mocked database session.
    """

    return MagicMock()


@pytest.fixture
def agent_action_service(
    mock_session: MagicMock,
    mock_repository: MagicMock,
) -> AgentActionService:
    """
    Create an AgentActionService with mocked dependencies.
    """

    return AgentActionService(
        session=mock_session,
        repository=mock_repository,
    )


@pytest.fixture
def action_entity() -> MagicMock:
    """
    Provide a mocked AgentAction entity.
    """

    entity = MagicMock(
        spec=AgentAction,
    )

    entity.id = "action-123"
    entity.execution_id = "execution-123"
    entity.agent_id = "agent-123"
    entity.action_type = ActionTypeEnum.TOOL_CALL
    entity.actor_type = ActorTypeEnum.USER

    return entity


@pytest.mark.asyncio
@patch(
    "application.services.agent_action.create_action_fingerprint",
)
@patch(
    "application.services.agent_action.AgentAction.from_dto",
)
async def test_create_returns_persisted_entity(
    mock_from_dto: MagicMock,
    mock_create_fingerprint: MagicMock,
    agent_action_service: AgentActionService,
    mock_repository: MagicMock,
    action_entity: MagicMock,
) -> None:
    """
    It should create and return the persisted AgentAction entity.
    """

    action = build_agent_action_request()

    mock_create_fingerprint.return_value = "fingerprint-123"

    mock_from_dto.return_value = action_entity

    mock_repository.create.return_value = action_entity

    result = await agent_action_service.create(
        action=action,
        user_id="user-123",
        tenant_id="tenant-123",
    )

    assert result is action_entity

    mock_create_fingerprint.assert_called_once_with(
        action,
    )

    mock_from_dto.assert_called_once_with(
        action=action,
        user_id="user-123",
        tenant_id="tenant-123",
        fingerprint="fingerprint-123",
    )

    mock_repository.create.assert_awaited_once_with(
        entity=action_entity,
    )


@pytest.mark.asyncio
@patch(
    "application.services.agent_action.create_action_fingerprint",
)
async def test_create_generates_fingerprint_before_persistence(
    mock_create_fingerprint: MagicMock,
    agent_action_service: AgentActionService,
    mock_repository: MagicMock,
    action_entity: MagicMock,
) -> None:
    """
    It should generate an action fingerprint before persistence.
    """

    action = build_agent_action_request()

    mock_create_fingerprint.return_value = "fingerprint-123"

    with patch(
        "application.services.agent_action.AgentAction.from_dto",
        return_value=action_entity,
    ) as mock_from_dto:
        mock_repository.create.return_value = action_entity

        await agent_action_service.create(
            action=action,
            user_id="user-123",
            tenant_id="tenant-123",
        )

    mock_create_fingerprint.assert_called_once_with(
        action,
    )

    mock_from_dto.assert_called_once_with(
        action=action,
        user_id="user-123",
        tenant_id="tenant-123",
        fingerprint="fingerprint-123",
    )


@pytest.mark.asyncio
@patch(
    "application.services.agent_action.create_action_fingerprint",
)
@patch(
    "application.services.agent_action.AgentAction.from_dto",
)
async def test_create_passes_correct_identity_to_entity(
    mock_from_dto: MagicMock,
    mock_create_fingerprint: MagicMock,
    agent_action_service: AgentActionService,
    mock_repository: MagicMock,
    action_entity: MagicMock,
) -> None:
    """
    It should pass user and tenant identity to AgentAction.from_dto.
    """

    action = build_agent_action_request()

    mock_create_fingerprint.return_value = "fingerprint-123"
    mock_from_dto.return_value = action_entity
    mock_repository.create.return_value = action_entity

    await agent_action_service.create(
        action=action,
        user_id="user-456",
        tenant_id="tenant-456",
    )

    mock_from_dto.assert_called_once_with(
        action=action,
        user_id="user-456",
        tenant_id="tenant-456",
        fingerprint="fingerprint-123",
    )


@pytest.mark.asyncio
@patch(
    "application.services.agent_action.create_action_fingerprint",
)
@patch(
    "application.services.agent_action.AgentAction.from_dto",
)
async def test_create_persists_constructed_entity(
    mock_from_dto: MagicMock,
    mock_create_fingerprint: MagicMock,
    agent_action_service: AgentActionService,
    mock_repository: MagicMock,
    action_entity: MagicMock,
) -> None:
    """
    It should pass the constructed SQLAlchemy entity to the repository.
    """

    action = build_agent_action_request()

    mock_create_fingerprint.return_value = "fingerprint-123"
    mock_from_dto.return_value = action_entity
    mock_repository.create.return_value = action_entity

    await agent_action_service.create(
        action=action,
        user_id="user-123",
        tenant_id="tenant-123",
    )

    mock_repository.create.assert_awaited_once_with(
        entity=action_entity,
    )


@pytest.mark.asyncio
@patch(
    "application.services.agent_action.create_action_fingerprint",
)
async def test_create_propagates_agent_action_error(
    mock_create_fingerprint: MagicMock,
    agent_action_service: AgentActionService,
    mock_repository: MagicMock,
) -> None:
    """
    It should propagate AgentActionError unchanged.
    """

    action = build_agent_action_request()

    error = AgentActionError(
        "Invalid agent action.",
    )

    mock_create_fingerprint.side_effect = error

    with pytest.raises(
        AgentActionError,
        match="Invalid agent action.",
    ):
        await agent_action_service.create(
            action=action,
            user_id="user-123",
            tenant_id="tenant-123",
        )

    mock_repository.create.assert_not_awaited()


@pytest.mark.asyncio
@patch(
    "application.services.agent_action.create_action_fingerprint",
)
async def test_create_wraps_unexpected_fingerprint_error(
    mock_create_fingerprint: MagicMock,
    agent_action_service: AgentActionService,
    mock_repository: MagicMock,
) -> None:
    """
    It should wrap unexpected fingerprint errors.
    """

    action = build_agent_action_request()

    error = RuntimeError(
        "fingerprint generation failed",
    )

    mock_create_fingerprint.side_effect = error

    with pytest.raises(
        AgentActionError,
        match="Failed to create agent action.",
    ) as exc_info:
        await agent_action_service.create(
            action=action,
            user_id="user-123",
            tenant_id="tenant-123",
        )

    assert exc_info.value.__cause__ is error

    mock_repository.create.assert_not_awaited()


@pytest.mark.asyncio
@patch(
    "application.services.agent_action.create_action_fingerprint",
)
@patch(
    "application.services.agent_action.AgentAction.from_dto",
)
async def test_create_wraps_unexpected_entity_creation_error(
    mock_from_dto: MagicMock,
    mock_create_fingerprint: MagicMock,
    agent_action_service: AgentActionService,
    mock_repository: MagicMock,
) -> None:
    """
    It should wrap unexpected entity construction errors.
    """

    action = build_agent_action_request()

    mock_create_fingerprint.return_value = "fingerprint-123"

    error = RuntimeError(
        "entity construction failed",
    )

    mock_from_dto.side_effect = error

    with pytest.raises(
        AgentActionError,
        match="Failed to create agent action.",
    ) as exc_info:
        await agent_action_service.create(
            action=action,
            user_id="user-123",
            tenant_id="tenant-123",
        )

    assert exc_info.value.__cause__ is error

    mock_repository.create.assert_not_awaited()


@pytest.mark.asyncio
@patch(
    "application.services.agent_action.create_action_fingerprint",
)
@patch(
    "application.services.agent_action.AgentAction.from_dto",
)
async def test_create_wraps_unexpected_repository_error(
    mock_from_dto: MagicMock,
    mock_create_fingerprint: MagicMock,
    agent_action_service: AgentActionService,
    mock_repository: MagicMock,
    action_entity: MagicMock,
) -> None:
    """
    It should wrap unexpected repository errors.
    """

    action = build_agent_action_request()

    mock_create_fingerprint.return_value = "fingerprint-123"
    mock_from_dto.return_value = action_entity

    error = RuntimeError(
        "database failure",
    )

    mock_repository.create.side_effect = error

    with pytest.raises(
        AgentActionError,
        match="Failed to create agent action.",
    ) as exc_info:
        await agent_action_service.create(
            action=action,
            user_id="user-123",
            tenant_id="tenant-123",
        )

    assert exc_info.value.__cause__ is error

    mock_create_fingerprint.assert_called_once_with(
        action,
    )

    mock_from_dto.assert_called_once_with(
        action=action,
        user_id="user-123",
        tenant_id="tenant-123",
        fingerprint="fingerprint-123",
    )

    mock_repository.create.assert_awaited_once_with(
        entity=action_entity,
    )
