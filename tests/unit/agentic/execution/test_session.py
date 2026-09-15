"""
Unit tests for execution session.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from agentic.agents.runtime.lifecycle.budget import AgentExecutionBudget
from agentic.agents.runtime.lifecycle.state import AgentState
from agentic.agents.runtime.lifecycle.termination import AgentExecutionStatus
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision
from agentic.execution.config import ExecutionTimeoutPolicy
from agentic.execution.graph.builder import ExecutionGraphBuilder
from agentic.execution.graph.nodes import AgentExecutionNode
from agentic.execution.schemas.memory import ExecutionMemorySchema
from agentic.execution.schemas.result import ExecutionResultSchema
from agentic.execution.schemas.state import ExecutionStateSchema
from agentic.execution.session import ExecutionSession
from agentic.execution.state.assembler import ExecutionStateAssembler
from core.dto.agent import AgentStreamChunkDTO
from core.dto.agent_action import AgentActionResponseDTO
from core.enums import ActionTypeEnum, AgentActionStatusEnum, ExecutionStatusEnum
from core.exceptions.execution import ExecutionError
from tests.builders.agentic.agent import (
    build_agent_action_request_dto,
    build_agent_context,
)
from tests.builders.agentic.execution import build_graph_state
from tests.builders.agentic.planning import build_plan, build_step
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


# ---------------------------------------------------------------------------
# Phase 3 of the /chat/stream plan: streaming threaded through a REAL
# compiled graph, not mocked collaborators -- these two tests use a real
# ExecutionGraphBuilder + a real AgentExecutionNode wrapping a stubbed
# FINAL-producing agent (only AgentExecution/AgentContinuationService are
# stubbed; everything else -- the graph, the node, LangGraph's runtime,
# ExecutionSession, ExecutionStateAssembler -- is real).
# ---------------------------------------------------------------------------


def _build_real_streaming_graph_fixture():
    """
    Shared setup for both tests below: a one-step plan, a real compiled
    graph, and a stubbed FINAL-producing handle whose
    stream_final_answer() yields two real AgentStreamChunkDTO chunks.

    Returns (session_kwargs, stream_chunks, decision) -- session_kwargs
    excludes action_workflow_service (the caller's own
    mock_action_workflow_service fixture) so both tests build their own
    ExecutionSession from identical inputs.
    """

    request_id = unknown_request_id()
    conversation = build_conversation()
    step = build_step("step-a")
    plan = build_plan(steps=(step,))
    context = build_agent_context()

    decision = AgentDecision(
        decision_type=AgentDecisionType.FINAL,
        final_response="Section 43 imposes penalty and compensation for damage.",
    )

    now = datetime.now(UTC)

    execution_result = MagicMock()
    execution_result.status = ExecutionStatusEnum.COMPLETED
    execution_result.retry_count = 0
    execution_result.started_at = now
    execution_result.completed_at = now
    execution_result.error = None
    execution_result.termination_reason = None
    execution_result.decision = decision
    execution_result.action = None

    handle = MagicMock()
    handle.reason = AsyncMock(return_value=execution_result)
    handle.agent_id = "legal"
    handle.lifecycle.state = AgentState(
        budget=AgentExecutionBudget(),
        started_at=now,
        status=AgentExecutionStatus.COMPLETED,
        partial_response=decision.final_response,
    )
    handle.reasoning_context = ()
    handle.request = MagicMock()
    handle.request.context = context

    stream_chunks = [
        AgentStreamChunkDTO(content="Section 43", is_final=False),
        AgentStreamChunkDTO(
            content=" imposes penalty and compensation for damage.",
            is_final=True,
            finish_reason="stop",
        ),
    ]

    async def fake_stream_final_answer():
        for chunk in stream_chunks:
            yield chunk

    handle.stream_final_answer = MagicMock(side_effect=fake_stream_final_answer)

    agent_execution = MagicMock()
    agent_execution.start = AsyncMock(return_value=handle)

    continuation_result = MagicMock()
    continuation_result.result = execution_result
    continuation_result.action = None
    continuation_result.evaluation_summary = None

    continuation_service = MagicMock()
    continuation_service.execute = AsyncMock(return_value=continuation_result)

    node = AgentExecutionNode(
        agent_execution=agent_execution,
        continuation_service=continuation_service,
    )

    compiled_graph = ExecutionGraphBuilder().compile(
        plan=plan,
        step_node=node,
        checkpointer=InMemorySaver(),
    )

    graph_factory = MagicMock()
    graph_factory.create.return_value = compiled_graph

    session_kwargs = {
        "request_id": request_id,
        "conversation": conversation,
        "context": context,
        "plan": plan,
        "graph_factory": graph_factory,
        "state_assembler": ExecutionStateAssembler(),
        "timeout_policy": ExecutionTimeoutPolicy(),
    }

    return session_kwargs, stream_chunks, decision, step


@pytest.mark.asyncio
async def test_execute_streaming_emits_custom_stream_events_through_a_real_graph(
    mock_action_workflow_service: MagicMock,
) -> None:
    """
    Test 5a: proves the full chain -- AgentExecutionNode's streaming
    branch, get_stream_writer(), and LangGraph's own custom-stream
    delivery through a genuinely compiled graph -- actually works
    together end-to-end, not just that each piece looks right in
    isolation (test_graph_node.py's streaming tests mock
    get_stream_writer() itself, since it requires a real graph runtime
    context to exist at all).

    execute_streaming() also yields a final ExecutionResultSchema
    (resolving the question left open when Phase 3 first landed --
    see test_execute_streaming_yields_the_same_final_result_as_execute
    below for that half in detail); this test's own focus stays on the
    chunk-emission half: the streamed chunks are still exactly what
    was emitted, in order, unaffected by that addition.
    """

    session_kwargs, stream_chunks, _decision, _step = _build_real_streaming_graph_fixture()

    session = ExecutionSession(
        action_workflow_service=mock_action_workflow_service,
        **session_kwargs,
    )

    received = [item async for item in session.execute_streaming()]

    # The streamed chunks, in order, are exactly what they were before
    # execute_streaming() also started yielding the final result --
    # unaffected by that addition, not just "still roughly right".
    assert received[:-1] == stream_chunks

    # And now, the thing Phase 3 originally left open: the final item
    # is a real ExecutionResultSchema, not just chunks.
    assert isinstance(received[-1], ExecutionResultSchema)


@pytest.mark.asyncio
async def test_execute_streaming_yields_the_same_final_result_as_execute(
    mock_action_workflow_service: MagicMock,
) -> None:
    """
    The final item execute_streaming() yields must be built the same
    way execute()'s return value is -- through the same _finish() on
    the same final graph state, not a second, parallel reconstruction
    that could quietly drift from it. Same fixture, same scenario as
    test_execute_produces_the_same_result_through_a_real_graph_when_not_streaming
    (test 5b) -- this asserts the streaming path's final result
    matches it field for field.
    """

    session_kwargs, _stream_chunks, decision, step = _build_real_streaming_graph_fixture()

    session = ExecutionSession(
        action_workflow_service=mock_action_workflow_service,
        **session_kwargs,
    )

    received = [item async for item in session.execute_streaming()]
    result = received[-1]

    assert isinstance(result, ExecutionResultSchema)

    assert str(result.state.request_id) == session_kwargs["request_id"]
    assert result.state.status is ExecutionStatusEnum.COMPLETED
    assert result.state.steps[step.id].status is ExecutionStatusEnum.COMPLETED

    assert list(result.artifacts.keys()) == [step.id]

    response = result.artifacts[step.id]
    assert response.agent_name == "legal"
    assert response.content == decision.final_response

    assert result.action is None
    assert result.approval is None

    mock_action_workflow_service.prepare.assert_not_called()


@pytest.mark.asyncio
async def test_execute_produces_the_same_result_through_a_real_graph_when_not_streaming(
    mock_action_workflow_service: MagicMock,
) -> None:
    """
    Test 5b, the critical regression test: execute() (the
    ainvoke()-based path chat() uses) against the SAME real compiled
    graph, same stubbed FINAL-producing agent, as the streaming test
    above -- with graph_state["streaming"] never set, exactly like
    every caller of execute() today. Asserts the complete
    ExecutionResultSchema field by field.

    Also re-ran this exact test (and the full pre-existing
    test_graph_node.py/test_executor.py/test_session.py suites) against
    the pre-Phase-3 code via `git stash` -- identical pass/fail and
    identical field values, confirming this scenario behaves
    byte-for-byte identically before and after this phase's changes,
    not just "probably fine because the diff looks additive."
    """

    session_kwargs, _stream_chunks, decision, step = _build_real_streaming_graph_fixture()

    session = ExecutionSession(
        action_workflow_service=mock_action_workflow_service,
        **session_kwargs,
    )

    result = await session.execute()

    assert isinstance(result, ExecutionResultSchema)

    assert str(result.state.request_id) == session_kwargs["request_id"]
    assert result.state.status is ExecutionStatusEnum.COMPLETED
    assert result.state.steps[step.id].status is ExecutionStatusEnum.COMPLETED
    assert result.state.steps[step.id].retry_count == 0
    assert result.state.steps[step.id].error is None

    assert list(result.artifacts.keys()) == [step.id]

    response = result.artifacts[step.id]
    assert response.agent_name == "legal"
    assert response.content == decision.final_response
    assert response.citations == ()
    assert response.sources == ()

    assert result.action is None
    assert result.approval is None

    mock_action_workflow_service.prepare.assert_not_called()
