"""
Decision-quality characterization tests for the real agent continuation runtime.

Testing rule:
    Keep the execution/lifecycle/continuation stack real.

Only external boundaries are controlled:
    - LLM structured decision output
    - RAG/retrieval evidence supplied to the execution
    - tool execution result

These tests intentionally do not create FakeLifecycle, FakeHandle,
FakeBudgetResult, or a replacement continuation implementation.

The suite is a characterization suite first. It records what the current
workflow actually does so that the missing decision-quality gate can be
implemented against observable behavior rather than assumptions.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from agentic.agents.legal import LegalAgent
from agentic.agents.runtime.continuation import AgentContinuationService
from agentic.agents.runtime.execution import AgentExecution
from agentic.agents.runtime.lifecycle.budget import AgentExecutionBudget
from agentic.agents.runtime.retry import RetryClassifier
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision, AgentToolCall
from agentic.decisions.validator import AgentDecisionValidator
from agentic.policy.agent_policy import StaticAgentPolicyProvider
from agentic.policy.guard import AgentPolicyGuard
from agentic.policy.schemas import AgentPolicy
from agentic.policy.tool_permission import ToolPermissionGuard
from agentic.registry.agent import AgentRegistry
from agentic.tools.result import ToolEvidence, ToolResult
from agentic.tools.runtime.invocation import ToolExecutionService
from core.dto.agent import AgentContextDTO, AgentRequestDTO
from core.dto.conversation import ConversationDTO
from core.dto.message import MessageDTO
from core.dto.tool import RetrievedContentDTO
from core.enums import MessageRoleEnum, RetrievalSourceEnum

AGENT_ID = "legal"
TOOL_NAME = "retriever"


def _final_decision(answer: str) -> AgentDecision:
    return AgentDecision(
        decision_type=AgentDecisionType.FINAL,
        final_response=answer,
    )


def _tool_decision() -> AgentDecision:
    return AgentDecision(
        decision_type=AgentDecisionType.TOOL_CALL,
        tool_call=AgentToolCall(
            tool_name=TOOL_NAME,
            parameters={"query": "test"},
        ),
    )


def _insufficient_answer_evaluator() -> tuple[MagicMock, MagicMock]:
    """Return synchronous mocks that model a numeric insufficient evaluation."""
    answer_evaluator = MagicMock()
    answer_evaluator.evaluate.return_value = SimpleNamespace(
        groundedness=0.0,
        relevance=0.0,
        completeness=0.0,
    )

    answer_quality_policy = MagicMock()
    answer_quality_policy.is_sufficient.return_value = False
    return answer_evaluator, answer_quality_policy


def _evidence(
    *,
    content: str,
    score: float | None,
    source_name: str = "test-rag",
) -> RetrievedContentDTO:
    return RetrievedContentDTO(
        source=RetrievalSourceEnum.DOCUMENT,
        source_name=source_name,
        content=content,
        score=score,
    )


def _tool_result(
    *,
    content: str,
    score: float | None,
    success: bool = True,
) -> ToolResult:
    return ToolResult(
        tool_name=TOOL_NAME,
        success=success,
        content=content,
        evidence=(
            ToolEvidence(
                content=content,
                score=score,
                source="test-rag",
            ),
        )
        if success
        else (),
        error=None if success else "tool failed",
    )


def _request() -> AgentRequestDTO:
    """
    Build the real request DTO using its actual dataclass contract.

    No fake request object or dataclass bypass is used. The nested
    conversation and runtime context are real DTOs as required by the
    current execution stack.
    """
    return AgentRequestDTO(
        conversation=ConversationDTO(
            messages=(
                MessageDTO(
                    role=MessageRoleEnum.USER,
                    content="What does the supplied evidence establish?",
                ),
            ),
        ),
        instruction="Answer the user's legal question using the supplied evidence.",
        arguments={},
        context=AgentContextDTO(
            user_id="test-user",
            execution_id="test-execution",
            thread_id="test-thread",
            conversation_event_id="test-event",
        ),
    )


@pytest.fixture
def llm_client() -> object:
    """
    Real BaseAgent receives a client-shaped object.

    Only the provider boundary is controlled; execution/lifecycle remains real.
    """

    client = AsyncMock()
    client.generate_structured = AsyncMock()
    return client


@pytest.fixture
def agent(llm_client: object) -> LegalAgent:
    return LegalAgent(
        llm_client=llm_client,
    )


@pytest.fixture
def execution(agent: LegalAgent) -> AgentExecution:
    registry = AgentRegistry()
    registry.register(component=agent)

    policy = AgentPolicy(
        agent_id=AGENT_ID,
        allowed_tools=frozenset({TOOL_NAME}),
    )

    policy_provider = StaticAgentPolicyProvider(
        policies={AGENT_ID: policy},
    )

    policy_guard = AgentPolicyGuard(
        tool_permission_guard=ToolPermissionGuard(),
    )

    return AgentExecution(
        agent_registry=registry,
        retry_policy=__import__(
            "agentic.execution.config",
            fromlist=["ExecutionRetryPolicy"],
        ).ExecutionRetryPolicy(max_attempts=1),
        retry_classifier=RetryClassifier(),
        decision_validator=AgentDecisionValidator(),
        agent_policy_provider=policy_provider,
        agent_policy_guard=policy_guard,
        agent_budget=AgentExecutionBudget(),
    )


@pytest.fixture
def tool_execution_service() -> ToolExecutionService:
    return ToolExecutionService(
        tool_registry=__import__(
            "agentic.registry.tool",
            fromlist=["ToolRegistry"],
        ).ToolRegistry(),
    )


@pytest.fixture
def collaboration_bus():
    from agentic.collaboration.bus import CollaborationBus

    return CollaborationBus()


async def _start_handle(
    execution: AgentExecution,
    *,
    reasoning_context: tuple[RetrievedContentDTO, ...] = (),
):
    return await execution.start(
        agent_id=AGENT_ID,
        request=_request(),
        reasoning_context=reasoning_context,
    )


@pytest.mark.asyncio
async def test_final_decision_completes_real_execution(
    execution: AgentExecution,
    agent: LegalAgent,
    llm_client: object,
) -> None:
    llm_client.generate_structured.return_value = _final_decision(
        "The answer is supported by the supplied evidence.",
    )

    handle = await _start_handle(execution)

    result = await handle.reason()

    assert result.status.value == "completed"
    assert result.decision is not None
    assert result.decision.decision_type is AgentDecisionType.FINAL
    assert result.partial_response == ("The answer is supported by the supplied evidence.")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "score",
    [None, 0.0, 0.1, 0.49, 0.5, 0.79, 0.8, 0.99, 1.0],
)
async def test_final_path_currently_does_not_apply_score_gate(
    execution: AgentExecution,
    llm_client: object,
    score: float | None,
) -> None:
    llm_client.generate_structured.return_value = _final_decision(
        "Answer.",
    )

    handle = await _start_handle(
        execution,
        reasoning_context=(
            _evidence(
                content="Evidence supplied for the answer.",
                score=score,
            ),
        ),
    )

    result = await handle.reason()

    # Characterizes the current gap: FINAL is accepted regardless of the
    # retrieval score because no independent sufficiency/quality gate exists.
    assert result.status.value == "completed"


@pytest.mark.asyncio
async def test_tool_result_is_real_continuation_input(
    execution: AgentExecution,
    agent: LegalAgent,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    llm_client.generate_structured.side_effect = [
        _tool_decision(),
        _final_decision("Final answer after retrieval."),
    ]

    tool_execution_service.execute = AsyncMock(
        return_value=_tool_result(
            content="Retrieved evidence supporting the answer.",
            score=0.91,
        ),
    )

    handle = await _start_handle(execution)
    initial = await handle.reason()

    answer_evaluator = MagicMock()
    answer_quality_policy = MagicMock()
    answer_quality_policy.is_sufficient.return_value = True

    continuation = AgentContinuationService(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
    )

    result = await continuation.execute(
        handle=handle,
        initial_result=initial,
    )

    assert result.result.decision is not None
    assert result.result.decision.decision_type is AgentDecisionType.FINAL
    assert result.tool_results == (tool_execution_service.execute.return_value,)
    assert len(handle.reasoning_context) == 1
    assert handle.reasoning_context[0].score == 0.91
    assert llm_client.generate_structured.await_count == 2


@pytest.mark.asyncio
async def test_failed_tool_terminates_real_lifecycle_without_next_reasoning(
    execution: AgentExecution,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    llm_client.generate_structured.return_value = _tool_decision()

    failed = _tool_result(
        content="",
        score=None,
        success=False,
    )
    tool_execution_service.execute = AsyncMock(return_value=failed)

    handle = await _start_handle(execution)
    initial = await handle.reason()

    answer_evaluator = MagicMock()
    answer_quality_policy = MagicMock()
    answer_quality_policy.is_sufficient.return_value = True

    continuation = AgentContinuationService(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
    )

    result = await continuation.execute(
        handle=handle,
        initial_result=initial,
    )

    assert result.result.status.value == "failed"
    assert result.result.termination_reason == "failed_tool"
    assert tool_execution_service.execute.await_count == 1
    assert llm_client.generate_structured.await_count == 1


@pytest.mark.asyncio
async def test_empty_tool_evidence_is_preserved_as_no_new_reasoning_context(
    execution: AgentExecution,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    llm_client.generate_structured.side_effect = [
        _tool_decision(),
        _final_decision("Answer after an empty tool response."),
    ]

    tool_execution_service.execute = AsyncMock(
        return_value=ToolResult(
            tool_name=TOOL_NAME,
            success=True,
            content="",
            evidence=(),
        ),
    )

    handle = await _start_handle(execution)
    initial = await handle.reason()

    answer_evaluator = MagicMock()
    answer_quality_policy = MagicMock()
    answer_quality_policy.is_sufficient.return_value = True

    continuation = AgentContinuationService(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
    )

    result = await continuation.execute(
        handle=handle,
        initial_result=initial,
    )

    assert result.result.status.value == "completed"
    assert len(handle.reasoning_context) == 0
    assert llm_client.generate_structured.await_count == 2


@pytest.mark.asyncio
async def test_low_score_evidence_currently_can_still_complete_final(
    execution: AgentExecution,
    llm_client: object,
) -> None:
    llm_client.generate_structured.return_value = _final_decision(
        "Unsupported answer.",
    )

    handle = await _start_handle(
        execution,
        reasoning_context=(
            _evidence(
                content="Weakly related evidence.",
                score=0.05,
            ),
        ),
    )

    result = await handle.reason()

    assert result.status.value == "completed"


@pytest.mark.asyncio
async def test_high_score_irrelevant_evidence_currently_can_still_complete_final(
    execution: AgentExecution,
    llm_client: object,
) -> None:
    llm_client.generate_structured.return_value = _final_decision(
        "This claim is unrelated to the retrieved evidence.",
    )

    handle = await _start_handle(
        execution,
        reasoning_context=(
            _evidence(
                content="A highly relevant result for a completely different question.",
                score=0.99,
            ),
        ),
    )

    result = await handle.reason()

    assert result.status.value == "completed"


@pytest.mark.asyncio
async def test_conflicting_evidence_currently_does_not_force_resolution(
    execution: AgentExecution,
    llm_client: object,
) -> None:
    llm_client.generate_structured.return_value = _final_decision(
        "One side of the conflict is correct.",
    )

    handle = await _start_handle(
        execution,
        reasoning_context=(
            _evidence(
                content="Source A says the deadline is 30 days.",
                score=0.94,
                source_name="source-a",
            ),
            _evidence(
                content="Source B says the deadline is 60 days.",
                score=0.93,
                source_name="source-b",
            ),
        ),
    )

    result = await handle.reason()

    assert result.status.value == "completed"


@pytest.mark.asyncio
async def test_final_is_not_compared_with_previous_final_answer(
    execution: AgentExecution,
    llm_client: object,
) -> None:
    llm_client.generate_structured.return_value = _final_decision(
        "Current answer.",
    )

    handle = await _start_handle(
        execution,
        reasoning_context=(
            _evidence(
                content="Supporting evidence.",
                score=0.90,
            ),
        ),
    )

    result = await handle.reason()

    assert result.partial_response == "Current answer."
    assert result.status.value == "completed"


# ---------------------------------------------------------------------------
# Decision-quality contract tests
# ---------------------------------------------------------------------------

"""
Decision-quality contract

A FINAL decision is not sufficient merely because:
    - it is schema-valid,
    - retrieval returned something,
    - a retrieval score is high, or
    - the model chose FINAL.

The execution runtime must independently determine whether the proposed
answer is sufficiently supported by the accumulated conversation/evidence.

Contract under test:
    1. Supported evidence + FINAL -> accept FINAL.
    2. No usable evidence + FINAL -> do not complete; continue through an
       available evidence-producing capability.
    3. High-score but semantically irrelevant evidence + FINAL -> do not
       complete; score alone is insufficient.
    4. Conflicting evidence + FINAL -> do not complete until the conflict is
       resolved or the runtime reaches an explicit terminal decision.
    5. Quality evaluation must not compare two answer strings merely to decide
       which answer is "better".
    6. Quality evaluation is a continuation/sufficiency concern and must
       preserve the existing request-scoped lifecycle and bounded controls.

These tests intentionally do not specify a numeric score threshold. Retrieval
score is an input signal, not the definition of semantic correctness.
"""


@pytest.mark.asyncio
async def test_final_without_evidence_must_not_be_accepted_as_terminal(
    execution: AgentExecution,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    """
    Missing evidence is the clearest insufficiency case.

    The LLM initially proposes FINAL, but the runtime must reject terminal
    completion and allow another bounded reasoning slice when an evidence
    producing tool is available.
    """
    llm_client.generate_structured.side_effect = [
        _final_decision("The contract permits termination immediately."),
        _tool_decision(),
    ]

    handle = await _start_handle(execution)
    initial = await handle.reason()

    # The contract under test only needs to prove that the rejected FINAL
    # triggers another bounded reasoning/action step. Keep tool execution at
    # its declared external boundary and make that attempted retrieval fail
    # deterministically rather than depending on global tool registration.
    tool_execution_service.execute = AsyncMock(
        return_value=_tool_result(
            content="",
            score=None,
            success=False,
        ),
    )

    answer_evaluator, answer_quality_policy = _insufficient_answer_evaluator()

    continuation = AgentContinuationService(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
    )

    result = await continuation.execute(
        handle=handle,
        initial_result=initial,
    )

    assert result.result.status.value != "completed"
    assert llm_client.generate_structured.await_count >= 2


@pytest.mark.asyncio
async def test_high_score_irrelevant_evidence_must_not_make_final_sufficient(
    execution: AgentExecution,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    """
    Retrieval score alone must never establish answer correctness.

    The evidence has a high score but does not address the user's question.
    The initial FINAL therefore requires another bounded reasoning/retrieval
    step instead of terminal completion.
    """
    llm_client.generate_structured.side_effect = [
        _final_decision("The notice period is 90 days."),
        _tool_decision(),
    ]

    handle = await _start_handle(
        execution,
        reasoning_context=(
            _evidence(
                content="This document concerns employee parking access.",
                score=0.99,
            ),
        ),
    )

    initial = await handle.reason()

    # The contract under test only needs to prove that the rejected FINAL
    # triggers another bounded reasoning/action step. Keep tool execution at
    # its declared external boundary and make that attempted retrieval fail
    # deterministically rather than depending on global tool registration.
    tool_execution_service.execute = AsyncMock(
        return_value=_tool_result(
            content="",
            score=None,
            success=False,
        ),
    )

    answer_evaluator, answer_quality_policy = _insufficient_answer_evaluator()

    continuation = AgentContinuationService(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
    )

    result = await continuation.execute(
        handle=handle,
        initial_result=initial,
    )

    assert result.result.status.value != "completed"
    assert llm_client.generate_structured.await_count >= 2


@pytest.mark.asyncio
async def test_conflicting_evidence_must_not_allow_unresolved_final(
    execution: AgentExecution,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    """
    Two materially conflicting sources require resolution.

    A high retrieval score on both sources does not establish which source is
    authoritative, so FINAL must not be accepted solely from those scores.
    """
    llm_client.generate_structured.side_effect = [
        _final_decision("The termination period is 30 days."),
        _tool_decision(),
    ]

    handle = await _start_handle(
        execution,
        reasoning_context=(
            _evidence(
                content="Termination requires thirty days notice.",
                score=0.96,
                source_name="source-a",
            ),
            _evidence(
                content="Termination requires sixty days notice.",
                score=0.95,
                source_name="source-b",
            ),
        ),
    )

    initial = await handle.reason()

    # The contract under test only needs to prove that the rejected FINAL
    # triggers another bounded reasoning/action step. Keep tool execution at
    # its declared external boundary and make that attempted retrieval fail
    # deterministically rather than depending on global tool registration.
    tool_execution_service.execute = AsyncMock(
        return_value=_tool_result(
            content="",
            score=None,
            success=False,
        ),
    )

    answer_evaluator, answer_quality_policy = _insufficient_answer_evaluator()

    continuation = AgentContinuationService(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
    )

    result = await continuation.execute(
        handle=handle,
        initial_result=initial,
    )

    assert result.result.status.value != "completed"
    assert llm_client.generate_structured.await_count >= 2


@pytest.mark.asyncio
async def test_insufficient_final_does_not_get_replaced_by_answer_string_comparison(
    execution: AgentExecution,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    """
    Quality is evidence/support based, not "new answer vs old answer" text
    similarity or preference.
    """
    llm_client.generate_structured.side_effect = [
        _final_decision("Initial unsupported answer."),
        _tool_decision(),
    ]

    handle = await _start_handle(
        execution,
        reasoning_context=(),
    )

    initial = await handle.reason()

    # The contract under test only needs to prove that the rejected FINAL
    # triggers another bounded reasoning/action step. Keep tool execution at
    # its declared external boundary and make that attempted retrieval fail
    # deterministically rather than depending on global tool registration.
    tool_execution_service.execute = AsyncMock(
        return_value=_tool_result(
            content="",
            score=None,
            success=False,
        ),
    )

    answer_evaluator, answer_quality_policy = _insufficient_answer_evaluator()

    continuation = AgentContinuationService(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
    )

    result = await continuation.execute(
        handle=handle,
        initial_result=initial,
    )

    assert result.result.status.value != "completed"
    assert llm_client.generate_structured.await_count >= 2
