"""
Unit tests for execution coordinator.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.dto.agent import AgentContextDTO
from src.execution.config import ExecutionTimeoutPolicy
from src.execution.executor import Executor
from src.execution.schemas.result import ExecutionResultSchema
from tests.builders.conversation import build_conversation
from tests.builders.planning import build_plan
from tests.helpers.identifiers import unknown_request_id


@pytest.mark.asyncio
@patch("src.execution.executor.ExecutionSession")
async def test_execute_creates_session_and_delegates(
    mock_session_class: MagicMock,
) -> None:
    """
    It should create a request-scoped execution session and delegate
    execution to it.
    """

    request_id = unknown_request_id()
    conversation = build_conversation()
    plan = build_plan()

    result = MagicMock(
        spec=ExecutionResultSchema,
    )

    session = MagicMock()
    session.execute = AsyncMock(
        return_value=result,
    )

    mock_session_class.return_value = session

    graph_factory = MagicMock()
    state_assembler = MagicMock()
    timeout_policy = ExecutionTimeoutPolicy()
    context = AgentContextDTO(
        uploaded_files=(),
        metadata={},
    )

    executor = Executor(
        graph_factory=graph_factory,
        state_assembler=state_assembler,
        timeout_policy=timeout_policy,
    )

    response = await executor.execute(
        request_id=request_id,
        conversation=conversation,
        plan=plan,
        context=context,
    )

    assert response is result

    mock_session_class.assert_called_once_with(
        request_id=request_id,
        conversation=conversation,
        context=context,
        plan=plan,
        graph_factory=graph_factory,
        state_assembler=state_assembler,
        timeout_policy=timeout_policy,
    )

    session.execute.assert_awaited_once()
