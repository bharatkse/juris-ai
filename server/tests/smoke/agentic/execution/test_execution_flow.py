"""
Juris-AI execution architecture smoke tests.

These tests cover the execution/collaboration changes introduced in the
current execution runtime:

- request-scoped AgentExecutionHandle
- bounded AgentLifecycle
- TOOL_CALL continuation
- DELEGATE continuation through CollaborationBus
- tool failure / budget termination
- graph dependency eligibility
- AgentExecutionNode -> continuation integration
- ExecutionStateAssembler terminal-state propagation
- business-action boundary
- approval boundary
- concurrent execution isolation

Run:

    pytest tests/smoke/execution/test_execution_flow.py -v -s
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from agentic.agents.runtime.continuation import AgentContinuationService
from agentic.agents.runtime.execution import AgentExecutionResult
from agentic.agents.runtime.lifecycle.budget import AgentExecutionBudget
from agentic.agents.runtime.lifecycle.lifecycle import AgentLifecycle
from agentic.agents.runtime.lifecycle.state import AgentState
from agentic.agents.runtime.lifecycle.termination import (
    AgentExecutionStatus,
    TerminationReason,
)
from agentic.collaboration.bus import CollaborationBus
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import (
    AgentDecision,
    AgentDelegation,
    AgentFailure,
    AgentToolCall,
    AgentUserInputRequest,
)
from agentic.execution.graph.builder import ExecutionGraphBuilder
from agentic.execution.graph.state import ExecutionGraphState, ExecutionStepUpdate
from agentic.execution.state import ExecutionStateAssembler
from agentic.registry.tool import ToolRegistry
from agentic.tools.base import Tool
from agentic.tools.runtime.invocation import ToolExecutionService
from core.dto.agent import AgentContextDTO, AgentRequestDTO
from core.dto.agent_action import AgentActionRequestDTO
from core.dto.conversation import ConversationDTO
from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from core.dto.tool import RetrievedContentDTO
from core.enums import (
    ActionTypeEnum,
    AgentTypeEnum,
    ExecutionModeEnum,
    ExecutionStatusEnum,
    IntentEnum,
    RetrievalSourceEnum,
)
from core.models.message import AgentMessageSchema

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class SmokeTool(Tool):
    name = "smoke_tool"
    description = "Deterministic smoke-test tool."

    def __init__(
        self,
        *,
        result: str = "tool result",
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict] = []

    async def execute(self, **kwargs) -> str:
        self.calls.append(kwargs)

        if self.error is not None:
            raise self.error

        return self.result


class SmokeCollaborationHandler:
    def __init__(self, result: object) -> None:
        self.result = result
        self.messages: list[AgentMessageSchema] = []

    async def handle_message(
        self,
        *,
        message: AgentMessageSchema,
    ) -> object:
        self.messages.append(message)
        return self.result


class SmokeActionWorkflowService:
    def __init__(self, *, approval_required: bool = False) -> None:
        self.approval_required_value = approval_required
        self.calls: list[dict] = []

    async def prepare(self, **kwargs):
        self.calls.append(kwargs)

        approval = (
            SimpleNamespace(approval_id="approval-smoke") if self.approval_required_value else None
        )

        return SimpleNamespace(
            action=SimpleNamespace(action_id="action-smoke"),
            approval=approval,
            approval_required=self.approval_required_value,
        )


class SmokeHandle:
    """
    Minimal request-scoped handle used to exercise the continuation loop.

    AgentExecutionHandle is deliberately not mocked globally; this double
    exposes only the public contract consumed by AgentContinuationService.
    """

    def __init__(
        self,
        *,
        decision: AgentDecision,
        action: AgentActionRequestDTO,
        next_result: AgentExecutionResult,
        budget: AgentExecutionBudget | None = None,
    ) -> None:
        self.request = _request()
        self.agent_id = "legal"

        self._last_decision = decision
        self._next_result = next_result
        self._reason_calls = 0
        self._reasoning_context: tuple[RetrievedContentDTO, ...] = ()

        state = AgentState(
            budget=budget or AgentExecutionBudget(),
            started_at=datetime.now(UTC),
        )
        self._lifecycle = AgentLifecycle(state=state)

        self._action = action

    @property
    def lifecycle(self) -> AgentLifecycle:
        return self._lifecycle

    @property
    def reasoning_context(self) -> tuple[RetrievedContentDTO, ...]:
        return self._reasoning_context

    def extend_reasoning_context(
        self,
        *,
        context: tuple[RetrievedContentDTO, ...],
    ) -> None:
        self._reasoning_context = (
            *self._reasoning_context,
            *context,
        )

    async def reason(self) -> AgentExecutionResult:
        self._reason_calls += 1
        return self._next_result

    def terminal_result(self) -> AgentExecutionResult:
        state = self._lifecycle.state

        return AgentExecutionResult(
            status=(
                ExecutionStatusEnum.PARTIAL
                if state.status is AgentExecutionStatus.PARTIAL
                else ExecutionStatusEnum.FAILED
            ),
            retry_count=0,
            started_at=state.started_at,
            completed_at=datetime.now(UTC),
            termination_reason=(
                state.termination_reason.value if state.termination_reason is not None else None
            ),
            error=None,
            partial_response=state.partial_response,
            decision=self._last_decision,
            action=None,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _request() -> AgentRequestDTO:
    return AgentRequestDTO(
        conversation=ConversationDTO(messages=()),
        instruction="Smoke-test execution.",
        arguments={},
        context=AgentContextDTO(
            user_id="user-smoke",
            execution_id="execution-smoke",
            thread_id="thread-smoke",
            conversation_event_id="event-smoke",
        ),
    )


def _action(
    *,
    action_type: ActionTypeEnum,
    tool_name: str | None = None,
    target_agent_id: str | None = None,
    parameters: dict | None = None,
) -> AgentActionRequestDTO:
    return AgentActionRequestDTO(
        execution_id="execution-smoke",
        thread_id="thread-smoke",
        conversation_event_id="event-smoke",
        agent_id="legal",
        action_type=action_type,
        tool_name=tool_name,
        target_agent_id=target_agent_id,
        parameters=parameters or {},
        reason="smoke test",
    )


def _final_decision(
    response: str = "Smoke test completed.",
) -> AgentDecision:
    return AgentDecision(
        decision_type=AgentDecisionType.FINAL,
        reason="done",
        final_response=response,
    )


def _tool_decision() -> AgentDecision:
    return AgentDecision(
        decision_type=AgentDecisionType.TOOL_CALL,
        reason="tool required",
        tool_call=AgentToolCall(
            tool_name="smoke_tool",
            parameters={"value": 42},
        ),
    )


def _delegate_decision() -> AgentDecision:
    return AgentDecision(
        decision_type=AgentDecisionType.DELEGATE,
        reason="specialist required",
        delegation=AgentDelegation(
            target_agent_id="contract",
            parameters={"clause": "termination"},
        ),
    )


def _need_input_decision() -> AgentDecision:
    return AgentDecision(
        decision_type=AgentDecisionType.NEED_INPUT,
        reason="missing information",
        user_input=AgentUserInputRequest(
            question="Which jurisdiction applies?",
        ),
    )


def _fail_decision() -> AgentDecision:
    return AgentDecision(
        decision_type=AgentDecisionType.FAIL,
        reason="execution cannot continue",
        failure=AgentFailure(
            code="SMOKE_FAILURE",
            message="Smoke-test failure.",
        ),
    )


def _result(
    *,
    status: ExecutionStatusEnum,
    decision: AgentDecision | None = None,
    action: AgentActionRequestDTO | None = None,
    termination_reason: str | None = None,
    error: str | None = None,
) -> AgentExecutionResult:
    started_at = datetime.now(UTC)

    return AgentExecutionResult(
        status=status,
        retry_count=0,
        started_at=started_at,
        completed_at=datetime.now(UTC),
        termination_reason=termination_reason,
        error=error,
        partial_response=None,
        decision=decision,
        action=action,
    )


def _graph_state(
    *,
    plan: ExecutionPlanDTO | None = None,
    updates: list[ExecutionStepUpdate] | None = None,
) -> ExecutionGraphState:
    return {
        "request_id": uuid4(),
        "started_at": datetime.now(UTC),
        "deadline": datetime.now(UTC),
        "conversation": ConversationDTO(messages=()),
        "context": AgentContextDTO(
            user_id="user-smoke",
            execution_id="execution-smoke",
            thread_id="thread-smoke",
            conversation_event_id="event-smoke",
        ),
        "plan": plan
        or ExecutionPlanDTO(
            intent=IntentEnum.GENERAL,
            mode=ExecutionModeEnum.SEQUENTIAL,
            steps=(),
        ),
        "reasoning_context": [],
        "execution_state_updates": updates or [],
        "memory_updates": [],
        "agent_decision_updates": [],
        "action": None,
    }


def _step(
    *,
    step_id: str,
    depends_on: tuple[str, ...] = (),
) -> ExecutionStepDTO:
    return ExecutionStepDTO(
        id=step_id,
        agent=AgentTypeEnum.LEGAL,
        instruction=f"Execute {step_id}.",
        depends_on=depends_on,
    )


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def test_smoke_lifecycle_budget_exhaustion_is_partial() -> None:
    lifecycle = AgentLifecycle(
        state=AgentState(
            budget=AgentExecutionBudget(max_iterations=1),
            started_at=datetime.now(UTC),
        ),
    )

    assert lifecycle.begin_iteration().allowed

    denied = lifecycle.begin_iteration()

    assert denied.allowed is False
    assert denied.reason is TerminationReason.PARTIAL_MAX_ITERATIONS
    assert lifecycle.state.status is AgentExecutionStatus.PARTIAL
    assert lifecycle.state.termination_reason is TerminationReason.PARTIAL_MAX_ITERATIONS


def test_smoke_lifecycle_repeated_action_is_bounded() -> None:
    """
    max_repeated_action=2 allows 2 consecutive repeats of the same action
    after its first occurrence (3 occurrences total), then denies the 3rd
    repeat -- per LoopBreaker.record_action's documented semantic.
    """
    lifecycle = AgentLifecycle(
        state=AgentState(
            budget=AgentExecutionBudget(max_repeated_action=2),
            started_at=datetime.now(UTC),
        ),
    )

    first = lifecycle.record_action("tool:smoke_tool")
    assert first.allowed

    second = lifecycle.record_action("tool:smoke_tool")
    assert second.allowed

    third = lifecycle.record_action("tool:smoke_tool")
    assert third.allowed

    fourth = lifecycle.record_action("tool:smoke_tool")

    assert not fourth.allowed
    assert fourth.reason is TerminationReason.PARTIAL_REPEATED_ACTION
    assert lifecycle.state.repeated_action_count == 2
    assert lifecycle.state.status is AgentExecutionStatus.PARTIAL
    assert lifecycle.state.termination_reason is TerminationReason.PARTIAL_REPEATED_ACTION


# ---------------------------------------------------------------------------
# Collaboration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smoke_collaboration_bus_routes_agent_message() -> None:
    bus = CollaborationBus()
    handler = SmokeCollaborationHandler("delegated result")

    bus.register(
        agent="contract",
        handler=handler,
    )

    request = _request()

    result = await bus.send(
        message=AgentMessageSchema(
            sender="legal",
            recipient="contract",
            capability=AgentDecisionType.DELEGATE.value,
            payload={
                "request": request,
                "parameters": {"clause": "termination"},
            },
        ),
    )

    assert result == "delegated result"
    assert len(handler.messages) == 1
    assert handler.messages[0].sender == "legal"
    assert handler.messages[0].recipient == "contract"
    assert handler.messages[0].payload["request"] is request


# ---------------------------------------------------------------------------
# Continuation: TOOL_CALL
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smoke_tool_call_executes_and_continues_reasoning() -> None:
    tool = SmokeTool(result="42")

    registry = ToolRegistry()
    registry.register(component=tool)

    continuation = AgentContinuationService(
        tool_execution_service=ToolExecutionService(
            tool_registry=registry,
        ),
        collaboration_bus=CollaborationBus(),
        answer_evaluator=AsyncMock(),
        answer_quality_policy=MagicMock(is_sufficient=MagicMock(return_value=True)),
        agent_policy_guard=MagicMock(),
    )

    decision = _tool_decision()
    action = _action(
        action_type=ActionTypeEnum.TOOL_CALL,
        tool_name="smoke_tool",
        parameters={"value": 42},
    )

    handle = SmokeHandle(
        decision=decision,
        action=action,
        next_result=_result(
            status=ExecutionStatusEnum.COMPLETED,
            decision=_final_decision("The answer is 42."),
        ),
    )

    result = await continuation.execute(
        handle=handle,
        initial_result=_result(
            status=ExecutionStatusEnum.COMPLETED,
            decision=decision,
            action=action,
        ),
    )

    assert result.result.status is ExecutionStatusEnum.COMPLETED
    assert result.result.decision is not None
    assert result.result.decision.decision_type is AgentDecisionType.FINAL

    assert len(result.tool_results) == 1
    assert result.tool_results[0].success is True
    assert tool.calls == [{"value": 42}]

    assert len(handle.reasoning_context) == 1
    assert handle.reasoning_context[0].source is RetrievalSourceEnum.MEMORY

    assert handle.reasoning_context[0].source_name == "smoke_tool"
    assert handle.reasoning_context[0].metadata["tool_name"] == "smoke_tool"
    assert handle.reasoning_context[0].metadata["tool_success"] is True


@pytest.mark.asyncio
async def test_smoke_tool_failure_is_failed_tool() -> None:
    tool = SmokeTool(
        error=RuntimeError("tool failed"),
    )

    registry = ToolRegistry()
    registry.register(component=tool)

    continuation = AgentContinuationService(
        tool_execution_service=ToolExecutionService(
            tool_registry=registry,
        ),
        collaboration_bus=CollaborationBus(),
        answer_evaluator=AsyncMock(),
        answer_quality_policy=MagicMock(is_sufficient=MagicMock(return_value=True)),
        agent_policy_guard=MagicMock(),
    )

    decision = _tool_decision()
    action = _action(
        action_type=ActionTypeEnum.TOOL_CALL,
        tool_name="smoke_tool",
    )

    handle = SmokeHandle(
        decision=decision,
        action=action,
        next_result=_result(
            status=ExecutionStatusEnum.COMPLETED,
            decision=_final_decision(),
        ),
    )

    result = await continuation.execute(
        handle=handle,
        initial_result=_result(
            status=ExecutionStatusEnum.COMPLETED,
            decision=decision,
            action=action,
        ),
    )

    assert result.result.status is ExecutionStatusEnum.FAILED
    assert result.result.termination_reason == TerminationReason.FAILED_TOOL.value
    assert result.tool_results[0].success is False


@pytest.mark.asyncio
async def test_smoke_tool_budget_denial_is_partial_not_failed() -> None:
    tool = SmokeTool(result="42")

    registry = ToolRegistry()
    registry.register(component=tool)

    continuation = AgentContinuationService(
        tool_execution_service=ToolExecutionService(
            tool_registry=registry,
        ),
        collaboration_bus=CollaborationBus(),
        answer_evaluator=AsyncMock(),
        answer_quality_policy=MagicMock(is_sufficient=MagicMock(return_value=True)),
        agent_policy_guard=MagicMock(),
    )

    decision = _tool_decision()
    action = _action(
        action_type=ActionTypeEnum.TOOL_CALL,
        tool_name="smoke_tool",
    )

    handle = SmokeHandle(
        decision=decision,
        action=action,
        next_result=_result(
            status=ExecutionStatusEnum.COMPLETED,
            decision=_final_decision(),
        ),
        budget=AgentExecutionBudget(max_tool_calls=1),
    )

    assert handle.lifecycle.begin_tool_call().allowed
    denied = handle.lifecycle.begin_tool_call()
    assert not denied.allowed
    assert denied.reason is TerminationReason.PARTIAL_MAX_TOOL_CALLS

    result = await continuation.execute(
        handle=handle,
        initial_result=_result(
            status=ExecutionStatusEnum.COMPLETED,
            decision=decision,
            action=action,
        ),
    )

    assert result.result.status is ExecutionStatusEnum.PARTIAL
    assert result.tool_results[0].success is False
    assert result.tool_results[0].execution_metadata["budget_exceeded"] is True
    assert tool.calls == []


# ---------------------------------------------------------------------------
# Continuation: DELEGATE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smoke_delegate_routes_through_bus_and_continues() -> None:
    bus = CollaborationBus()
    handler = SmokeCollaborationHandler(
        "contract specialist result",
    )

    bus.register(
        agent="contract",
        handler=handler,
    )

    continuation = AgentContinuationService(
        tool_execution_service=ToolExecutionService(
            tool_registry=ToolRegistry(),
        ),
        collaboration_bus=bus,
        answer_evaluator=AsyncMock(),
        answer_quality_policy=MagicMock(is_sufficient=MagicMock(return_value=True)),
        agent_policy_guard=MagicMock(),
    )

    decision = _delegate_decision()
    action = _action(
        action_type=ActionTypeEnum.AGENT_CALL,
        target_agent_id="contract",
    )

    handle = SmokeHandle(
        decision=decision,
        action=action,
        next_result=_result(
            status=ExecutionStatusEnum.COMPLETED,
            decision=_final_decision(
                "Contract specialist result incorporated.",
            ),
        ),
    )

    result = await continuation.execute(
        handle=handle,
        initial_result=_result(
            status=ExecutionStatusEnum.COMPLETED,
            decision=decision,
            action=action,
        ),
    )

    assert result.result.status is ExecutionStatusEnum.COMPLETED
    assert result.result.decision is not None
    assert result.result.decision.decision_type is AgentDecisionType.FINAL

    assert len(handler.messages) == 1
    assert handler.messages[0].sender == "legal"
    assert handler.messages[0].recipient == "contract"

    assert len(handle.reasoning_context) == 1
    assert handle.reasoning_context[0].source is RetrievalSourceEnum.MEMORY
    assert handle.reasoning_context[0].metadata["source_type"] == "agent_delegation"


@pytest.mark.asyncio
async def test_smoke_delegate_budget_denial_is_partial() -> None:
    bus = CollaborationBus()
    handler = SmokeCollaborationHandler("must not run")

    bus.register(
        agent="contract",
        handler=handler,
    )

    continuation = AgentContinuationService(
        tool_execution_service=ToolExecutionService(
            tool_registry=ToolRegistry(),
        ),
        collaboration_bus=bus,
        answer_evaluator=AsyncMock(),
        answer_quality_policy=MagicMock(is_sufficient=MagicMock(return_value=True)),
        agent_policy_guard=MagicMock(),
    )

    decision = _delegate_decision()
    action = _action(
        action_type=ActionTypeEnum.AGENT_CALL,
        target_agent_id="contract",
    )

    handle = SmokeHandle(
        decision=decision,
        action=action,
        next_result=_result(
            status=ExecutionStatusEnum.COMPLETED,
            decision=_final_decision(),
        ),
        budget=AgentExecutionBudget(max_agent_hops=1),
    )

    assert handle.lifecycle.begin_agent_hop().allowed

    denied = handle.lifecycle.begin_agent_hop()

    assert not denied.allowed
    assert denied.reason is TerminationReason.PARTIAL_MAX_AGENT_HOPS

    result = await continuation.execute(
        handle=handle,
        initial_result=_result(
            status=ExecutionStatusEnum.COMPLETED,
            decision=decision,
            action=action,
        ),
    )

    assert result.result.status is ExecutionStatusEnum.PARTIAL
    assert handler.messages == []


# ---------------------------------------------------------------------------
# Graph dependency semantics
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dependency_status",
    [
        ExecutionStatusEnum.FAILED,
        ExecutionStatusEnum.PARTIAL,
        ExecutionStatusEnum.SKIPPED,
    ],
)
async def test_smoke_dependency_non_completed_status_skips_step(
    dependency_status: ExecutionStatusEnum,
) -> None:
    executed = False

    async def step_node(
        state: ExecutionGraphState,
        *,
        step: ExecutionStepDTO,
    ):
        nonlocal executed
        executed = True
        return {}

    dependency = ExecutionStepUpdate(
        step_id="step-a",
        status=dependency_status,
        retry_count=0,
        started_at=None,
        completed_at=None,
        error="dependency not completed",
        termination_reason=dependency_status.value,
    )

    step = _step(
        step_id="step-b",
        depends_on=("step-a",),
    )

    node = ExecutionGraphBuilder._create_step_node(
        step=step,
        step_node=step_node,
    )

    result = await node(
        _graph_state(updates=[dependency]),
    )

    assert executed is False
    assert result["execution_state_updates"][0]["status"] is ExecutionStatusEnum.SKIPPED


def test_smoke_latest_dependency_update_wins() -> None:
    step = _step(
        step_id="step-b",
        depends_on=("step-a",),
    )

    state = _graph_state(
        updates=[
            ExecutionStepUpdate(
                step_id="step-a",
                status=ExecutionStatusEnum.FAILED,
                retry_count=0,
                started_at=None,
                completed_at=None,
                error="old failure",
                termination_reason=TerminationReason.FAILED_LLM.value,
            ),
            ExecutionStepUpdate(
                step_id="step-a",
                status=ExecutionStatusEnum.COMPLETED,
                retry_count=1,
                started_at=None,
                completed_at=None,
                error=None,
                termination_reason=TerminationReason.COMPLETED.value,
            ),
        ],
    )

    assert ExecutionGraphBuilder._dependencies_completed(
        state=state,
        step=step,
    )


# ---------------------------------------------------------------------------
# State assembly
# ---------------------------------------------------------------------------


def test_smoke_assembler_propagates_partial_and_termination_reason() -> None:
    request_id = uuid4()

    plan = ExecutionPlanDTO(
        intent=IntentEnum.GENERAL,
        mode=ExecutionModeEnum.SEQUENTIAL,
        steps=(_step(step_id="answer"),),
    )

    update = ExecutionStepUpdate(
        step_id="answer",
        status=ExecutionStatusEnum.PARTIAL,
        retry_count=1,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        error=None,
        termination_reason=TerminationReason.PARTIAL_MAX_ITERATIONS.value,
    )

    graph_state = _graph_state(
        plan=plan,
        updates=[update],
    )
    graph_state["request_id"] = request_id

    assembled = ExecutionStateAssembler().assemble_state(
        graph_state=graph_state,
    )

    assert assembled.request_id == request_id
    assert assembled.status is ExecutionStatusEnum.PARTIAL
    assert assembled.steps["answer"].status is ExecutionStatusEnum.PARTIAL
    assert (
        assembled.steps["answer"].termination_reason
        == TerminationReason.PARTIAL_MAX_ITERATIONS.value
    )


def test_smoke_assembler_failed_takes_precedence_over_partial() -> None:
    plan = ExecutionPlanDTO(
        intent=IntentEnum.GENERAL,
        mode=ExecutionModeEnum.SEQUENTIAL,
        steps=(
            _step(step_id="partial"),
            _step(step_id="failed"),
        ),
    )

    updates = [
        ExecutionStepUpdate(
            step_id="partial",
            status=ExecutionStatusEnum.PARTIAL,
            retry_count=0,
            started_at=None,
            completed_at=None,
            error=None,
            termination_reason=TerminationReason.PARTIAL_MAX_ITERATIONS.value,
        ),
        ExecutionStepUpdate(
            step_id="failed",
            status=ExecutionStatusEnum.FAILED,
            retry_count=0,
            started_at=None,
            completed_at=None,
            error="failed",
            termination_reason=TerminationReason.FAILED_LLM.value,
        ),
    ]

    assembled = ExecutionStateAssembler().assemble_state(
        graph_state=_graph_state(
            plan=plan,
            updates=updates,
        ),
    )

    assert assembled.status is ExecutionStatusEnum.FAILED


# ---------------------------------------------------------------------------
# Concurrent request isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smoke_concurrent_continuations_keep_request_context_isolated() -> None:
    tool = SmokeTool(result="shared tool result")

    registry = ToolRegistry()
    registry.register(component=tool)

    continuation = AgentContinuationService(
        tool_execution_service=ToolExecutionService(
            tool_registry=registry,
        ),
        collaboration_bus=CollaborationBus(),
        answer_evaluator=AsyncMock(),
        answer_quality_policy=MagicMock(is_sufficient=MagicMock(return_value=True)),
        agent_policy_guard=MagicMock(),
    )

    decision = _tool_decision()

    handle_a = SmokeHandle(
        decision=decision,
        action=_action(
            action_type=ActionTypeEnum.TOOL_CALL,
            tool_name="smoke_tool",
        ),
        next_result=_result(
            status=ExecutionStatusEnum.COMPLETED,
            decision=_final_decision("A"),
        ),
    )

    handle_b = SmokeHandle(
        decision=decision,
        action=_action(
            action_type=ActionTypeEnum.TOOL_CALL,
            tool_name="smoke_tool",
        ),
        next_result=_result(
            status=ExecutionStatusEnum.COMPLETED,
            decision=_final_decision("B"),
        ),
    )

    result_a, result_b = await asyncio.gather(
        continuation.execute(
            handle=handle_a,
            initial_result=_result(
                status=ExecutionStatusEnum.COMPLETED,
                decision=decision,
                action=handle_a._action,
            ),
        ),
        continuation.execute(
            handle=handle_b,
            initial_result=_result(
                status=ExecutionStatusEnum.COMPLETED,
                decision=decision,
                action=handle_b._action,
            ),
        ),
    )

    assert result_a.result.decision is not None
    assert result_b.result.decision is not None
    assert result_a.result.decision.final_response == "A"
    assert result_b.result.decision.final_response == "B"

    assert handle_a.reasoning_context is not handle_b.reasoning_context
    assert len(handle_a.reasoning_context) == 1
    assert len(handle_b.reasoning_context) == 1
