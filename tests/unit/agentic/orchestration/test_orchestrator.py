"""
Unit tests for AIOrchestrator.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from agentic.execution.aggregation.response import ResponseAggregator
from agentic.execution.schemas.result import ExecutionResultSchema
from agentic.execution.schemas.state import ExecutionStateSchema
from agentic.execution.validation.response import ResponseValidator
from agentic.orchestration.orchestrator import AIOrchestrator
from agentic.orchestration.schemas.response import OrchestratorResponse
from core.dto.planning import ExecutionPlanDTO
from core.enums import ExecutionModeEnum, ExecutionStatusEnum, IntentEnum
from tests.builders.agentic.orchestrator import build_orchestrator_request


def build_failed_execution_result() -> ExecutionResultSchema:
    """
    An execution result shaped exactly like a non-gated tool-call
    failure: terminal FAILED status, no artifacts (AgentResponseMapper
    never ran because FINAL was never reached -- see
    AgentContinuationService's TOOL_CALL branch in continuation.py).
    """

    return ExecutionResultSchema(
        state=ExecutionStateSchema(
            request_id=uuid4(),
            status=ExecutionStatusEnum.FAILED,
        ),
        artifacts={},
        action=None,
        approval=None,
    )


@pytest.fixture
def orchestrator() -> AIOrchestrator:
    planner = MagicMock()
    planner.create_plan = AsyncMock(
        return_value=ExecutionPlanDTO(
            intent=IntentEnum.GENERAL,
            mode=ExecutionModeEnum.SEQUENTIAL,
            steps=(),
        )
    )

    executor = MagicMock()
    executor.execute = AsyncMock(
        return_value=build_failed_execution_result(),
    )

    authorization = MagicMock()
    authorization.authorize_request = MagicMock()

    return AIOrchestrator(
        planner=planner,
        executor=executor,
        # Real validator/aggregator -- this test exists specifically to
        # prove ResponseAggregator.aggregate() is never reached (and
        # its EmptyAggregationError never raised) when there are no
        # agent responses, so both must be the real implementations,
        # not mocks that would hide the bug.
        validator=ResponseValidator(),
        aggregator=ResponseAggregator(),
        authorization=authorization,
    )


@pytest.mark.asyncio
async def test_handle_returns_graceful_fallback_on_non_gated_tool_failure(
    orchestrator: AIOrchestrator,
) -> None:
    """
    A tool-call failure that ends a turn without ever reaching FINAL
    (any tool, not just a gated one) must not crash handle() with an
    unhandled EmptyAggregationError -- it should return a normal
    OrchestratorResponse carrying a clear, user-facing explanation.
    """

    request = build_orchestrator_request()

    response = await orchestrator.handle(
        request=request,
        action_workflow_service=MagicMock(),
    )

    assert isinstance(response, OrchestratorResponse)
    assert response.content
    assert "wasn't able to complete" in response.content
    assert response.citations == []
    assert response.sources == []
    assert response.action is None
    assert response.approval is None


@pytest.mark.asyncio
async def test_handle_still_raises_for_a_real_orchestration_error(
    orchestrator: AIOrchestrator,
) -> None:
    """
    The fallback is specific to "no agent responses" -- an unrelated,
    genuine failure (e.g. planning itself blowing up) must still
    propagate, not be swallowed by the same fallback path.
    """

    orchestrator._planner.create_plan = AsyncMock(
        side_effect=RuntimeError("planner exploded"),
    )

    request = build_orchestrator_request()

    with pytest.raises(RuntimeError, match="planner exploded"):
        await orchestrator.handle(
            request=request,
            action_workflow_service=MagicMock(),
        )
