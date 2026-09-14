"""
Unit tests for execution session.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from agentic.decisions.decision import AgentDecisionType
from agentic.execution.config import ExecutionTimeoutPolicy
from agentic.execution.schemas.memory import ExecutionMemorySchema
from agentic.execution.schemas.state import ExecutionStateSchema
from agentic.execution.session import ExecutionSession
from core.dto.agent_action import AgentActionResponseDTO
from core.enums import ActionTypeEnum, AgentActionStatusEnum, ExecutionStatusEnum
from core.exceptions.execution import ExecutionError
from tests.builders.agentic.agent import (
    build_agent_action_request_dto,
    build_agent_context,
)
from tests.builders.agentic.execution import build_graph_state
from tests.builders.agentic.planning import build_plan
from tests.builders.application.conversation import build_conversation
from tests.unit.helpers.identifiers import unknown_request_id


def _with_session_required_graph_keys(graph_state: dict) -> dict:
    """
    Ensure the graph-state builder result contains every key consumed
    directly by ExecutionSession.
    """
    graph_state.setdefault("agent_decision_updates", [])
    graph_state.setdefault("action", None)
    return graph_state


@pytest.mark.asyncio
async def test_execute_session(
    mock_action_workflow_service: MagicMock,
) -> None:
    """
    It should create the execution graph, invoke it, assemble the
    execution state and return the execution result.
    """

    request_id = unknown_request_id()
    conversation = build_conversation()
    plan = build_plan()
    context = build_agent_context()

    graph_state = _with_session_required_graph_keys(
        build_graph_state(
            request_id=request_id,
            plan=plan,
        ),
    )

    graph = MagicMock()
    graph.ainvoke = AsyncMock(return_value=graph_state)

    graph_factory = MagicMock()
    graph_factory.create.return_value = graph

    state = ExecutionStateSchema(
        request_id=request_id,
        status=ExecutionStatusEnum.COMPLETED,
    )

    memory = ExecutionMemorySchema(
        artifacts={
            "step-a.response": "Executed A",
        },
    )

    state_assembler = MagicMock()
    state_assembler.assemble_state.return_value = state
    state_assembler.assemble_memory.return_value = memory
    state_assembler.assemble_action.return_value = None

    preparation_result = MagicMock()
    preparation_result.action = None
    preparation_result.approval = None

    mock_action_workflow_service.prepare = AsyncMock(
        return_value=preparation_result,
    )

    session = ExecutionSession(
        request_id=request_id,
        conversation=conversation,
        context=context,
        plan=plan,
        graph_factory=graph_factory,
        state_assembler=state_assembler,
        timeout_policy=ExecutionTimeoutPolicy(),
        action_workflow_service=mock_action_workflow_service,
    )

    result = await session.execute()

    graph_factory.create.assert_called_once_with(plan=plan)
    graph.ainvoke.assert_awaited_once()

    state_assembler.assemble_state.assert_called_once_with(
        graph_state=graph_state,
    )
    state_assembler.assemble_memory.assert_called_once_with(
        graph_state=graph_state,
    )
    state_assembler.assemble_action.assert_called_once_with(
        graph_state=graph_state,
    )

    mock_action_workflow_service.prepare.assert_not_awaited()

    assert result.state is state
    assert result.artifacts == {
        "step-a.response": "Executed A",
    }
    assert result.action is None
    assert result.approval is None


@pytest.mark.asyncio
async def test_execute_session_passes_tenant_id_to_action_workflow(
    mock_action_workflow_service: MagicMock,
) -> None:
    """
    It should pass the tenant identifier through the real runtime workflow.
    """

    request_id = unknown_request_id()
    conversation = build_conversation()
    plan = build_plan()
    context = build_agent_context(
        user_id="user-123",
        execution_id="execution-123",
        thread_id="thread-123",
        conversation_event_id="event-123",
    )

    action_request = build_agent_action_request_dto(
        execution_id="execution-123",
        thread_id="thread-123",
        conversation_event_id="event-123",
        agent_id="agent-123",
        action_type=ActionTypeEnum.TOOL_CALL,
        tool_name="lookup_document",
    )

    action_response = AgentActionResponseDTO(
        action_id="actn-123",
        execution_id="execution-123",
        thread_id="thread-123",
        conversation_event_id="event-123",
        agent_id="agent-123",
        action_type=ActionTypeEnum.TOOL_CALL,
        actor_type=action_request.actor_type,
        tool_name="lookup_document",
        target_agent_id=None,
        resource_type=None,
        resource_id=None,
        parameters={},
        reason="",
        status=AgentActionStatusEnum.DRAFT,
        fingerprint="abc123",
    )

    graph_state = _with_session_required_graph_keys(
        build_graph_state(
            request_id=request_id,
            plan=plan,
        ),
    )
    graph_state["action"] = action_request

    graph = MagicMock()
    graph.ainvoke = AsyncMock(return_value=graph_state)

    graph_factory = MagicMock()
    graph_factory.create.return_value = graph

    state_assembler = MagicMock()
    state_assembler.assemble_state.return_value = ExecutionStateSchema(
        request_id=request_id,
        status=ExecutionStatusEnum.COMPLETED,
    )
    state_assembler.assemble_memory.return_value = ExecutionMemorySchema(
        artifacts={},
    )
    state_assembler.assemble_action.return_value = action_request

    preparation_result = MagicMock()
    preparation_result.action = action_response
    preparation_result.approval = None
    preparation_result.approval_required = False

    mock_action_workflow_service.prepare = AsyncMock(
        return_value=preparation_result,
    )

    session = ExecutionSession(
        request_id=request_id,
        conversation=conversation,
        context=context,
        plan=plan,
        graph_factory=graph_factory,
        state_assembler=state_assembler,
        timeout_policy=ExecutionTimeoutPolicy(),
        action_workflow_service=mock_action_workflow_service,
    )

    result = await session.execute()

    mock_action_workflow_service.prepare.assert_awaited_once_with(
        user_id="user-123",
        tenant_id="user-123",
        action=action_request,
    )

    assert result.action is action_response
    assert result.approval is None


@pytest.mark.asyncio
async def test_execute_session_does_not_forward_internal_tool_call_action(
    mock_action_workflow_service: MagicMock,
) -> None:
    """
    It should not forward an internal TOOL_CALL action to the business
    action workflow boundary.
    """

    request_id = unknown_request_id()
    conversation = build_conversation()
    plan = build_plan()
    context = build_agent_context()

    action_request = build_agent_action_request_dto(
        execution_id="execution-123",
        thread_id="thread-123",
        conversation_event_id="event-123",
        agent_id="agent-123",
        action_type=ActionTypeEnum.TOOL_CALL,
        tool_name="lookup_document",
    )

    graph_state = _with_session_required_graph_keys(
        build_graph_state(
            request_id=request_id,
            plan=plan,
        ),
    )
    graph_state["action"] = action_request

    latest_decision = MagicMock()
    latest_decision.decision_type = AgentDecisionType.TOOL_CALL
    graph_state["agent_decision_updates"] = [
        {"decision": latest_decision},
    ]

    graph = MagicMock()
    graph.ainvoke = AsyncMock(return_value=graph_state)

    graph_factory = MagicMock()
    graph_factory.create.return_value = graph

    state_assembler = MagicMock()
    state_assembler.assemble_state.return_value = ExecutionStateSchema(
        request_id=request_id,
        status=ExecutionStatusEnum.COMPLETED,
    )
    state_assembler.assemble_memory.return_value = ExecutionMemorySchema(
        artifacts={},
    )
    state_assembler.assemble_action.return_value = action_request

    session = ExecutionSession(
        request_id=request_id,
        conversation=conversation,
        context=context,
        plan=plan,
        graph_factory=graph_factory,
        state_assembler=state_assembler,
        timeout_policy=ExecutionTimeoutPolicy(),
        action_workflow_service=mock_action_workflow_service,
    )

    result = await session.execute()

    mock_action_workflow_service.prepare.assert_not_awaited()
    assert result.action is None
    assert result.approval is None


@pytest.mark.asyncio
async def test_execute_session_sets_waiting_for_approval_status(
    mock_action_workflow_service: MagicMock,
) -> None:
    """
    It should mark the assembled execution state as waiting for approval
    when ActionWorkflowService reports that approval is required.
    """

    request_id = unknown_request_id()
    conversation = build_conversation()
    plan = build_plan()
    context = build_agent_context()

    action_request = build_agent_action_request_dto(
        execution_id="execution-123",
        thread_id="thread-123",
        conversation_event_id="event-123",
        agent_id="agent-123",
        action_type=ActionTypeEnum.TOOL_CALL,
        tool_name="lookup_document",
    )

    graph_state = _with_session_required_graph_keys(
        build_graph_state(
            request_id=request_id,
            plan=plan,
        ),
    )
    graph_state["action"] = action_request

    graph = MagicMock()
    graph.ainvoke = AsyncMock(return_value=graph_state)

    graph_factory = MagicMock()
    graph_factory.create.return_value = graph

    state = ExecutionStateSchema(
        request_id=request_id,
        status=ExecutionStatusEnum.PARTIAL,
    )

    state_assembler = MagicMock()
    state_assembler.assemble_state.return_value = state
    state_assembler.assemble_memory.return_value = ExecutionMemorySchema(
        artifacts={},
    )
    state_assembler.assemble_action.return_value = action_request

    preparation_result = MagicMock()
    # ExecutionResultSchema requires AgentActionResponseDTO for ``action``.
    preparation_result.action = AgentActionResponseDTO(
        action_id="actn-123",
        execution_id="execution-123",
        thread_id="thread-123",
        conversation_event_id="event-123",
        agent_id="agent-123",
        action_type=ActionTypeEnum.TOOL_CALL,
        actor_type=action_request.actor_type,
        tool_name="lookup_document",
        target_agent_id=None,
        resource_type=None,
        resource_id=None,
        parameters={},
        reason="",
        status=AgentActionStatusEnum.DRAFT,
        fingerprint="abc123",
    )
    # This test is about the status transition. The result schema permits
    # ``approval=None``, so no concrete ApprovalResponseDTO is required.
    preparation_result.approval = None
    preparation_result.approval_required = True

    mock_action_workflow_service.prepare = AsyncMock(
        return_value=preparation_result,
    )

    session = ExecutionSession(
        request_id=request_id,
        conversation=conversation,
        context=context,
        plan=plan,
        graph_factory=graph_factory,
        state_assembler=state_assembler,
        timeout_policy=ExecutionTimeoutPolicy(),
        action_workflow_service=mock_action_workflow_service,
    )

    result = await session.execute()

    assert result.state is state
    assert result.state.status is ExecutionStatusEnum.WAITING_FOR_APPROVAL
    assert result.action is preparation_result.action
    assert result.approval is None


@pytest.mark.asyncio
async def test_execute_session_propagates_graph_execution_failure(
    mock_action_workflow_service: MagicMock,
) -> None:
    """
    It should propagate a graph execution failure.
    """

    request_id = unknown_request_id()
    conversation = build_conversation()
    context = build_agent_context()
    plan = build_plan()

    graph = MagicMock()
    graph.ainvoke = AsyncMock(
        side_effect=RuntimeError("Graph execution failed."),
    )

    graph_factory = MagicMock()
    graph_factory.create.return_value = graph

    state_assembler = MagicMock()

    session = ExecutionSession(
        request_id=request_id,
        conversation=conversation,
        context=context,
        plan=plan,
        graph_factory=graph_factory,
        state_assembler=state_assembler,
        timeout_policy=ExecutionTimeoutPolicy(),
        action_workflow_service=mock_action_workflow_service,
    )

    with pytest.raises(RuntimeError, match="Graph execution failed."):
        await session.execute()

    graph_factory.create.assert_called_once_with(plan=plan)
    graph.ainvoke.assert_awaited_once()

    state_assembler.assemble_state.assert_not_called()
    state_assembler.assemble_memory.assert_not_called()


@pytest.mark.asyncio
async def test_execute_session_times_out(
    mock_action_workflow_service: MagicMock,
) -> None:
    """
    It should raise a timeout when graph execution exceeds the
    configured execution timeout.
    """

    request_id = unknown_request_id()
    conversation = build_conversation()
    context = build_agent_context()
    plan = build_plan()

    graph = MagicMock()

    async def slow_invoke(*args, **kwargs):
        await asyncio.sleep(0.1)

    graph.ainvoke = slow_invoke

    graph_factory = MagicMock()
    graph_factory.create.return_value = graph

    state_assembler = MagicMock()

    session = ExecutionSession(
        request_id=request_id,
        conversation=conversation,
        context=context,
        plan=plan,
        graph_factory=graph_factory,
        state_assembler=state_assembler,
        timeout_policy=ExecutionTimeoutPolicy(timeout_seconds=0.01),
        action_workflow_service=mock_action_workflow_service,
    )

    with pytest.raises(
        ExecutionError,
        match="Execution timed out after 0.01 seconds.",
    ):
        await session.execute()

    graph_factory.create.assert_called_once_with(plan=plan)
    state_assembler.assemble_state.assert_not_called()
    state_assembler.assemble_memory.assert_not_called()
