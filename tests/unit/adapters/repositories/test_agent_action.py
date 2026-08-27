"""
Unit tests for AgentActionRepository.
"""

from __future__ import annotations

import pytest

from tests.factories.agent_action import AgentActionFactory
from tests.helpers.identifiers import unknown_agent_action_id


@pytest.mark.asyncio
async def test_create_persists_agent_action(
    agent_action_repository,
) -> None:
    """
    It should persist an agent action.
    """

    action = AgentActionFactory.build()

    created = await agent_action_repository.create(
        entity=action,
    )

    assert created.id == action.id
    assert created.execution_id == action.execution_id
    assert created.thread_id == action.thread_id
    assert created.agent_id == action.agent_id
    assert created.action_type == action.action_type
    assert created.status == action.status


@pytest.mark.asyncio
async def test_create_sets_timestamps(
    agent_action_repository,
) -> None:
    """
    It should populate timestamps.
    """

    action = AgentActionFactory.build()

    created = await agent_action_repository.create(
        entity=action,
    )

    assert created.created_at is not None
    assert created.updated_at is not None


@pytest.mark.asyncio
async def test_get_returns_existing_agent_action(
    agent_action_repository,
) -> None:
    """
    It should retrieve an existing agent action.
    """

    action = await agent_action_repository.create(
        entity=AgentActionFactory.build(),
    )

    found = await agent_action_repository.get(
        action_id=action.id,
    )

    assert found is not None
    assert found.id == action.id
    assert found.execution_id == action.execution_id
    assert found.thread_id == action.thread_id
    assert found.agent_id == action.agent_id
    assert found.action_type == action.action_type
    assert found.status == action.status


@pytest.mark.asyncio
async def test_get_returns_none_when_agent_action_does_not_exist(
    agent_action_repository,
) -> None:
    """
    It should return None for an unknown agent action.
    """

    found = await agent_action_repository.get(
        action_id=unknown_agent_action_id(),
    )

    assert found is None


@pytest.mark.asyncio
async def test_get_by_execution_returns_agent_actions(
    agent_action_repository,
) -> None:
    """
    It should return all agent actions for an execution.
    """

    first = await agent_action_repository.create(
        entity=AgentActionFactory.build(
            execution_id="execution-1",
        ),
    )

    second = await agent_action_repository.create(
        entity=AgentActionFactory.build(
            execution_id="execution-1",
        ),
    )

    # Different execution should not be returned.
    await agent_action_repository.create(
        entity=AgentActionFactory.build(
            execution_id="execution-2",
        ),
    )

    actions = await agent_action_repository.get_by_execution(
        execution_id="execution-1",
    )

    assert len(actions) == 2

    assert {action.id for action in actions} == {
        first.id,
        second.id,
    }


@pytest.mark.asyncio
async def test_get_by_execution_returns_empty_list_when_no_actions_exist(
    agent_action_repository,
) -> None:
    """
    It should return an empty list when no actions exist for an execution.
    """

    actions = await agent_action_repository.get_by_execution(
        execution_id="execution-unknown",
    )

    assert actions == []


@pytest.mark.asyncio
async def test_get_by_execution_returns_actions_in_creation_order(
    agent_action_repository,
) -> None:
    """
    It should return actions ordered by creation time.
    """

    first = await agent_action_repository.create(
        entity=AgentActionFactory.build(
            execution_id="execution-1",
        ),
    )

    second = await agent_action_repository.create(
        entity=AgentActionFactory.build(
            execution_id="execution-1",
        ),
    )

    actions = await agent_action_repository.get_by_execution(
        execution_id="execution-1",
    )

    assert [action.id for action in actions] == [
        first.id,
        second.id,
    ]


@pytest.mark.asyncio
async def test_get_does_not_return_action_from_another_id(
    agent_action_repository,
) -> None:
    """
    It should only return the requested agent action.
    """

    action = await agent_action_repository.create(
        entity=AgentActionFactory.build(),
    )

    other = await agent_action_repository.create(
        entity=AgentActionFactory.build(),
    )

    found = await agent_action_repository.get(
        action_id=other.id,
    )

    assert found is not None
    assert found.id == other.id
    assert found.id != action.id
