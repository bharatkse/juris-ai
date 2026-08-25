"""
Unit tests for agent action API dependencies.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.agent_action import (
    get_agent_action_repository,
    get_agent_action_service,
)
from src.repositories.agent_action import AgentActionRepository
from src.services.agent_action import AgentActionService


def test_get_agent_action_repository_returns_repository() -> None:
    """
    It should create an AgentActionRepository.
    """

    session = MagicMock(
        spec=AsyncSession,
    )

    result = get_agent_action_repository(
        session=session,
    )

    assert isinstance(
        result,
        AgentActionRepository,
    )


def test_get_agent_action_repository_uses_supplied_session() -> None:
    """
    It should pass the supplied session to the repository.
    """

    session = MagicMock(
        spec=AsyncSession,
    )

    result = get_agent_action_repository(
        session=session,
    )

    assert result._session is session


def test_get_agent_action_service_returns_service() -> None:
    """
    It should create an AgentActionService.
    """

    session = MagicMock(
        spec=AsyncSession,
    )
    repository = MagicMock(
        spec=AgentActionRepository,
    )

    result = get_agent_action_service(
        session=session,
        repository=repository,
    )

    assert isinstance(
        result,
        AgentActionService,
    )


def test_get_agent_action_service_uses_supplied_dependencies() -> None:
    """
    It should pass the supplied session and repository to the service.
    """

    session = MagicMock(
        spec=AsyncSession,
    )
    repository = MagicMock(
        spec=AgentActionRepository,
    )

    result = get_agent_action_service(
        session=session,
        repository=repository,
    )

    assert result._session is session
    assert result._repository is repository
