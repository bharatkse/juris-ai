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

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

from agentic.agents.legal import LegalAgent
from agentic.agents.runtime.continuation import (
    NO_SOURCES_ANSWER_MESSAGE,
    SEED_RETRIEVAL_TOP_K,
    UNVERIFIED_ANSWER_MESSAGE,
    AgentContinuationService,
)
from agentic.agents.runtime.execution import AgentExecution
from agentic.agents.runtime.lifecycle.budget import AgentExecutionBudget
from agentic.agents.runtime.lifecycle.termination import TerminationReason
from agentic.agents.runtime.retry import RetryClassifier
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision, AgentToolCall
from agentic.decisions.validator import AgentDecisionValidator
from agentic.evaluation.answer import AnswerQualityPolicy
from agentic.execution.aggregation.mapper import AgentResponseMapper
from agentic.policy.agent_policy import StaticAgentPolicyProvider
from agentic.policy.guard import AgentPolicyGuard
from agentic.policy.schemas import AgentPolicy
from agentic.policy.tool_permission import ToolPermissionGuard
from agentic.registry.agent import AgentRegistry
from agentic.registry.tool import ToolRegistry
from agentic.tools.result import ToolEvidence, ToolResult
from agentic.tools.retrieval import NO_RESULTS_CONTENT, RETRIEVAL_FAILED_CONTENT
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


def _sufficient_answer_evaluator(
    *,
    groundedness: float = 0.91,
    relevance: float = 0.87,
) -> tuple[AsyncMock, MagicMock]:
    """
    Return mocks that model a numeric SUFFICIENT evaluation -- the
    is_sufficient()=True path _gate_final takes when it accepts a
    FINAL answer and reports its AnswerEvaluationSummary.
    """

    answer_evaluator = AsyncMock()
    answer_evaluator.evaluate.return_value = SimpleNamespace(
        groundedness=groundedness,
        relevance=relevance,
        completeness=0.9,
        groundedness_detail=SimpleNamespace(applicable=True),
    )

    answer_quality_policy = MagicMock()
    answer_quality_policy.is_sufficient.return_value = True
    answer_quality_policy.min_groundedness = 0.50
    answer_quality_policy.min_relevance = 0.60
    return answer_evaluator, answer_quality_policy


def _insufficient_answer_evaluator() -> tuple[AsyncMock, MagicMock]:
    """Return mocks that model a numeric insufficient evaluation.

    ``evaluate`` is awaited by the real continuation code, so it must be an
    AsyncMock; ``is_sufficient`` stays synchronous. groundedness_detail and
    the policy's min_* thresholds are real (non-Mock) values because
    _gate_final now compares them directly (to decide whether to force
    corrective retrieval) rather than only calling is_sufficient().
    """
    answer_evaluator = AsyncMock()
    answer_evaluator.evaluate.return_value = SimpleNamespace(
        groundedness=0.0,
        relevance=0.0,
        completeness=0.0,
        groundedness_detail=SimpleNamespace(applicable=True),
    )

    answer_quality_policy = MagicMock()
    answer_quality_policy.is_sufficient.return_value = False
    answer_quality_policy.min_groundedness = 0.70
    answer_quality_policy.min_relevance = 0.70
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
        tool_registry=ToolRegistry(),
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

    answer_evaluator = AsyncMock()
    answer_quality_policy = MagicMock()
    answer_quality_policy.is_sufficient.return_value = True

    continuation = AgentContinuationService(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
        agent_policy_guard=MagicMock(),
        compliance_log=AsyncMock(),
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


def _sufficient_policy_continuation(
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> AgentContinuationService:
    answer_quality_policy = MagicMock()
    answer_quality_policy.is_sufficient.return_value = True

    return AgentContinuationService(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=AsyncMock(),
        answer_quality_policy=answer_quality_policy,
        agent_policy_guard=MagicMock(),
        compliance_log=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_failed_tool_is_fed_back_and_the_model_reasons_again(
    execution: AgentExecution,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    """
    A failed tool call no longer ends the turn: the model is told why
    (the sanitized error) and reasons again. Before, the turn ended with
    failed_tool and the user got the generic fallback.
    """

    llm_client.generate_structured.side_effect = [
        _tool_decision(),
        _final_decision("Answer from the evidence available."),
    ]
    tool_execution_service.execute = AsyncMock(
        return_value=_tool_result(content="", score=None, success=False),
    )

    handle = await _start_handle(execution)
    initial = await handle.reason()

    result = await _sufficient_policy_continuation(
        tool_execution_service, collaboration_bus
    ).execute(handle=handle, initial_result=initial)

    assert result.result.decision.final_response == "Answer from the evidence available."
    assert llm_client.generate_structured.await_count == 2

    second_prompt = llm_client.generate_structured.await_args_list[1].kwargs["request"]
    assert any(
        "Your call to tool 'retriever' failed: tool failed" in message.content
        for message in second_prompt.messages
    )


@pytest.mark.asyncio
async def test_a_repeating_tool_failure_still_ends_the_execution(
    execution: AgentExecution,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    """
    Feeding failures back is bounded: the model repeating the same failing
    call hits the repeated-action budget and the execution ends.
    """

    llm_client.generate_structured.return_value = _tool_decision()
    tool_execution_service.execute = AsyncMock(
        return_value=_tool_result(content="", score=None, success=False),
    )

    handle = await _start_handle(execution)
    initial = await handle.reason()

    result = await asyncio.wait_for(
        _sufficient_policy_continuation(tool_execution_service, collaboration_bus).execute(
            handle=handle,
            initial_result=initial,
        ),
        timeout=5,
    )

    assert result.result.status.value != "completed"
    assert result.result.termination_reason == "partial_repeated_action"
    # max_repeated_action=2: the identical call runs three times, and the
    # fourth proposal of it ends the execution.
    assert tool_execution_service.execute.await_count == 3
    assert llm_client.generate_structured.await_count == 4


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

    answer_evaluator = AsyncMock()
    answer_quality_policy = MagicMock()
    answer_quality_policy.is_sufficient.return_value = True

    continuation = AgentContinuationService(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
        agent_policy_guard=MagicMock(),
        compliance_log=AsyncMock(),
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
        agent_policy_guard=MagicMock(),
        compliance_log=AsyncMock(),
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
        agent_policy_guard=MagicMock(),
        compliance_log=AsyncMock(),
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
        agent_policy_guard=MagicMock(),
        compliance_log=AsyncMock(),
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
        agent_policy_guard=MagicMock(),
        compliance_log=AsyncMock(),
    )

    result = await continuation.execute(
        handle=handle,
        initial_result=initial,
    )

    assert result.result.status.value != "completed"
    assert llm_client.generate_structured.await_count >= 2


@pytest.mark.asyncio
async def test_tool_call_records_compliance_log_entries(
    execution: AgentExecution,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    """
    A real tool call that returns evidence must record both a
    TOOL_CALL_EXECUTED and a RETRIEVAL_PERFORMED compliance log entry
    -- written from inside the LangGraph @task body for replay safety
    (see AgentContinuationService._execute_tool's docstring), verified
    here via the real continuation runtime rather than a mock of the
    task machinery itself.
    """

    request = AgentRequestDTO(
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
            request_id="55673c69-323d-49d2-95c0-c4cba4cbaacc",
        ),
    )

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

    handle = await execution.start(
        agent_id=AGENT_ID,
        request=request,
        reasoning_context=(),
    )
    initial = await handle.reason()

    answer_evaluator = AsyncMock()
    answer_quality_policy = MagicMock()
    answer_quality_policy.is_sufficient.return_value = True

    compliance_log = AsyncMock()

    continuation = AgentContinuationService(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
        agent_policy_guard=MagicMock(),
        compliance_log=compliance_log,
    )

    await continuation.execute(
        handle=handle,
        initial_result=initial,
    )

    compliance_log.record_tool_call_executed.assert_awaited_once_with(
        request_id=UUID("55673c69-323d-49d2-95c0-c4cba4cbaacc"),
        user_id="test-user",
        tenant_id="test-user",
        thread_id="test-thread",
        agent_id=AGENT_ID,
        tool_name=TOOL_NAME,
        success=True,
    )

    compliance_log.record_retrieval_performed.assert_awaited_once()
    retrieval_call = compliance_log.record_retrieval_performed.await_args.kwargs
    assert retrieval_call["request_id"] == UUID("55673c69-323d-49d2-95c0-c4cba4cbaacc")
    assert len(retrieval_call["retrieved"]) == 1
    assert retrieval_call["retrieved"][0].content == "Retrieved evidence supporting the answer."


@pytest.mark.asyncio
async def test_tool_call_without_evidence_records_tool_call_but_not_retrieval(
    execution: AgentExecution,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    """
    A successful tool call with no explicit ToolEvidence (e.g. a
    send-email/slack action) must record TOOL_CALL_EXECUTED but must
    NOT be misreported as a RETRIEVAL_PERFORMED -- see
    _record_tool_call_compliance's comment on why this is gated on
    result.evidence specifically, not the converted reasoning-context
    fallback.
    """

    request = AgentRequestDTO(
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
            request_id="55673c69-323d-49d2-95c0-c4cba4cbaacc",
        ),
    )

    llm_client.generate_structured.side_effect = [
        _tool_decision(),
        _final_decision("Final answer after the action."),
    ]

    tool_execution_service.execute = AsyncMock(
        return_value=ToolResult(
            tool_name=TOOL_NAME,
            success=True,
            content="Action completed successfully.",
            evidence=(),
        ),
    )

    handle = await execution.start(
        agent_id=AGENT_ID,
        request=request,
        reasoning_context=(),
    )
    initial = await handle.reason()

    answer_evaluator = AsyncMock()
    answer_quality_policy = MagicMock()
    answer_quality_policy.is_sufficient.return_value = True

    compliance_log = AsyncMock()

    continuation = AgentContinuationService(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
        agent_policy_guard=MagicMock(),
        compliance_log=compliance_log,
    )

    await continuation.execute(
        handle=handle,
        initial_result=initial,
    )

    compliance_log.record_tool_call_executed.assert_awaited_once()
    compliance_log.record_retrieval_performed.assert_not_awaited()


@pytest.mark.asyncio
async def test_tool_call_skips_compliance_write_when_request_id_missing(
    execution: AgentExecution,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    """
    AgentContextDTO.request_id defaults to "" -- _record_tool_call_
    compliance must skip gracefully (not raise UUID("")) rather than
    fail a real tool call over a missing correlation id.
    """

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

    # _request() (the shared helper) builds a context with no
    # request_id set, i.e. the default "".
    handle = await _start_handle(execution)
    initial = await handle.reason()

    answer_evaluator = AsyncMock()
    answer_quality_policy = MagicMock()
    answer_quality_policy.is_sufficient.return_value = True

    compliance_log = AsyncMock()

    continuation = AgentContinuationService(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
        agent_policy_guard=MagicMock(),
        compliance_log=compliance_log,
    )

    await continuation.execute(
        handle=handle,
        initial_result=initial,
    )

    compliance_log.record_tool_call_executed.assert_not_awaited()
    compliance_log.record_retrieval_performed.assert_not_awaited()


@pytest.mark.asyncio
async def test_accepted_final_carries_real_evaluation_summary(
    execution: AgentExecution,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    """
    A FINAL decision _gate_final accepts (is_sufficient() -> True)
    must carry the accepted evaluation's real groundedness/relevance
    on AgentContinuationResult.evaluation_summary -- the threading
    this test exists for. Purely additive: does not touch is_sufficient
    itself (mocked True here, same as any other accepted-FINAL test).
    """

    llm_client.generate_structured.return_value = _final_decision(
        "The answer is supported by the supplied evidence.",
    )

    handle = await _start_handle(
        execution,
        reasoning_context=(_evidence(content="Supporting evidence.", score=0.9),),
    )
    initial = await handle.reason()

    answer_evaluator, answer_quality_policy = _sufficient_answer_evaluator(
        groundedness=0.91,
        relevance=0.87,
    )

    continuation = AgentContinuationService(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
        agent_policy_guard=MagicMock(),
        compliance_log=AsyncMock(),
    )

    result = await continuation.execute(
        handle=handle,
        initial_result=initial,
    )

    assert result.evaluation_summary is not None
    assert result.evaluation_summary.groundedness == 0.91
    assert result.evaluation_summary.relevance == 0.87

    answer_evaluator.evaluate.assert_awaited_once()


@pytest.mark.asyncio
async def test_final_with_empty_answer_carries_no_evaluation_summary(
    execution: AgentExecution,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    """
    _gate_final's "no answer" early-exit never calls the evaluator at
    all -- evaluation_summary must stay None for this accepted-FINAL
    path, same as any other case where no evaluation was accepted.
    """

    llm_client.generate_structured.return_value = _final_decision("")

    handle = await _start_handle(execution)
    initial = await handle.reason()

    answer_evaluator, answer_quality_policy = _sufficient_answer_evaluator()

    continuation = AgentContinuationService(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
        agent_policy_guard=MagicMock(),
        compliance_log=AsyncMock(),
    )

    result = await continuation.execute(
        handle=handle,
        initial_result=initial,
    )

    assert result.evaluation_summary is None
    answer_evaluator.evaluate.assert_not_awaited()


@pytest.mark.asyncio
async def test_evaluation_summary_flows_into_mapped_agent_response_metadata(
    execution: AgentExecution,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    """
    End of the threading path: AgentResponseMapper.map() (the same
    call AgentExecutionNode makes) must surface evaluation_summary's
    fields on AgentResponseDTO.metadata -- what the orchestrator's
    compliance write actually reads. Also covers metadata["evidence_text"],
    the same threading for the guardrail's PII-provenance check
    (AIOrchestrator._evidence_text) -- both are populated from this
    one map() call, so one real-runtime test covers both.
    """

    llm_client.generate_structured.return_value = _final_decision(
        "The answer is supported by the supplied evidence.",
    )

    handle = await _start_handle(
        execution,
        reasoning_context=(_evidence(content="Supporting evidence.", score=0.9),),
    )
    initial = await handle.reason()

    answer_evaluator, answer_quality_policy = _sufficient_answer_evaluator(
        groundedness=0.75,
        relevance=0.65,
    )

    continuation = AgentContinuationService(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
        agent_policy_guard=MagicMock(),
        compliance_log=AsyncMock(),
    )

    result = await continuation.execute(
        handle=handle,
        initial_result=initial,
    )

    mapper = AgentResponseMapper(agent_name=AGENT_ID)
    response = mapper.map(
        state=handle.lifecycle.state,
        execution_id=handle.request.context.execution_id,
        context=handle.reasoning_context,
        evaluation_summary=result.evaluation_summary,
    )

    assert response.metadata["groundedness"] == 0.75
    assert response.metadata["relevance"] == 0.65
    # The real, untruncated evidence text -- this test's reasoning_context
    # was seeded with _evidence(content="Supporting evidence.", ...).
    assert response.metadata["evidence_text"] == "Supporting evidence."
    assert response.metadata["answer_verified"] is True


# ---------------------------------------------------------------------------
# S5: a FINAL answer the gate rejects must never be returned when nothing is
# left to improve it. Before the fix, the exhausted branch returned a result
# whose decision was still the rejected FINAL, and the loop re-gated it
# forever (the evaluator was called until the graph timeout).
# ---------------------------------------------------------------------------

REJECTED_ANSWER = "Section 99Z lets either party terminate without notice."


def _execution_with_budget(agent: LegalAgent, **budget: int) -> AgentExecution:
    registry = AgentRegistry()
    registry.register(component=agent)

    return AgentExecution(
        agent_registry=registry,
        retry_policy=__import__(
            "agentic.execution.config",
            fromlist=["ExecutionRetryPolicy"],
        ).ExecutionRetryPolicy(max_attempts=1),
        retry_classifier=RetryClassifier(),
        decision_validator=AgentDecisionValidator(),
        agent_policy_provider=StaticAgentPolicyProvider(
            policies={
                AGENT_ID: AgentPolicy(
                    agent_id=AGENT_ID,
                    allowed_tools=frozenset({TOOL_NAME}),
                ),
            },
        ),
        agent_policy_guard=AgentPolicyGuard(
            tool_permission_guard=ToolPermissionGuard(),
        ),
        tool_registry=ToolRegistry(),
        agent_budget=AgentExecutionBudget(**budget),
    )


def _yielding_insufficient_answer_evaluator() -> tuple[AsyncMock, MagicMock]:
    """
    _insufficient_answer_evaluator(), but evaluate() yields to the event
    loop, so asyncio.wait_for() can stop a runaway gating loop.
    """

    answer_evaluator, answer_quality_policy = _insufficient_answer_evaluator()
    evaluation = answer_evaluator.evaluate.return_value

    async def evaluate(**_kwargs):
        await asyncio.sleep(0)
        return evaluation

    answer_evaluator.evaluate.side_effect = evaluate
    return answer_evaluator, answer_quality_policy


def _assert_rejected_answer_replaced(handle, result) -> None:
    assert result.result.status.value == "partial"
    assert result.result.termination_reason == TerminationReason.QUALITY_GATE_EXHAUSTED.value
    assert result.evaluation_summary is not None
    assert result.evaluation_summary.verified is False

    response = AgentResponseMapper(agent_name=AGENT_ID).map(
        state=handle.lifecycle.state,
        execution_id=handle.request.context.execution_id,
        context=handle.reasoning_context,
        evaluation_summary=result.evaluation_summary,
    )

    assert response.content == UNVERIFIED_ANSWER_MESSAGE
    assert REJECTED_ANSWER not in response.content
    assert response.metadata["answer_verified"] is False
    assert response.metadata["termination_reason"] == "quality_gate_exhausted"
    assert response.metadata["groundedness"] == 0.0
    assert response.metadata["relevance"] == 0.0


@pytest.mark.asyncio
async def test_rejected_final_is_replaced_when_step_budget_is_exhausted(
    agent: LegalAgent,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    llm_client.generate_structured.return_value = _final_decision(REJECTED_ANSWER)

    # One step: the initial reasoning uses it, so the gate's retry is denied.
    execution = _execution_with_budget(agent, max_total_steps=1)
    handle = await _start_handle(
        execution,
        reasoning_context=(_evidence(content="Section 43 covers damage.", score=0.8),),
    )
    initial = await handle.reason()

    answer_evaluator, answer_quality_policy = _yielding_insufficient_answer_evaluator()

    continuation = AgentContinuationService(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
        agent_policy_guard=MagicMock(),
        compliance_log=AsyncMock(),
    )

    result = await asyncio.wait_for(
        continuation.execute(handle=handle, initial_result=initial),
        timeout=5,
    )

    _assert_rejected_answer_replaced(handle, result)
    assert answer_evaluator.evaluate.await_count == 1
    assert llm_client.generate_structured.await_count == 1


@pytest.mark.asyncio
async def test_rejected_final_is_replaced_when_the_retry_ends_without_a_new_decision(
    agent: LegalAgent,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    """
    The gate's corrective retrieval runs, but the follow-up reasoning is
    denied by the step budget, so no new answer is produced: the
    rejected answer must still not come back.
    """

    llm_client.generate_structured.return_value = _final_decision(REJECTED_ANSWER)

    # Step 1: initial reasoning. Step 2: the gate's retry. The reasoning
    # after corrective retrieval would need step 3.
    execution = _execution_with_budget(agent, max_total_steps=2)
    handle = await _start_handle(execution)
    initial = await handle.reason()

    tool_execution_service.execute = AsyncMock(
        return_value=_tool_result(content="Unrelated retrieved text.", score=0.4),
    )

    answer_evaluator, answer_quality_policy = _yielding_insufficient_answer_evaluator()

    continuation = AgentContinuationService(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
        agent_policy_guard=MagicMock(),
        compliance_log=AsyncMock(),
    )

    result = await asyncio.wait_for(
        continuation.execute(handle=handle, initial_result=initial),
        timeout=5,
    )

    tool_execution_service.execute.assert_awaited_once()
    _assert_rejected_answer_replaced(handle, result)
    assert answer_evaluator.evaluate.await_count == 1


# ---------------------------------------------------------------------------
# A1: grounding is required. Evidence is seeded before the first reasoning
# call; an answer with no evidence to check it against is rejected, and when
# retrieval finds nothing the fixed "no sources" answer replaces it.
# ---------------------------------------------------------------------------


def _no_evidence_evaluation(**_kwargs):
    return SimpleNamespace(
        groundedness=0.0,
        relevance=0.9,
        completeness=0.9,
        correctness=None,
        citation_precision=0.0,
        citation_coverage=0.0,
        groundedness_detail=SimpleNamespace(applicable=False),
    )


def _grounded_evaluation(**_kwargs):
    return SimpleNamespace(
        groundedness=0.9,
        relevance=0.9,
        completeness=0.9,
        correctness=None,
        citation_precision=0.0,
        citation_coverage=0.0,
        groundedness_detail=SimpleNamespace(applicable=True),
    )


def _continuation(
    *,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
    answer_evaluator=None,
    answer_quality_policy=None,
) -> AgentContinuationService:
    return AgentContinuationService(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator or AsyncMock(),
        answer_quality_policy=answer_quality_policy or AnswerQualityPolicy(require_evidence=True),
        agent_policy_guard=AgentPolicyGuard(
            tool_permission_guard=ToolPermissionGuard(),
        ),
        compliance_log=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_seed_evidence_retrieves_for_the_user_question_before_reasoning(
    execution: AgentExecution,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    tool_execution_service.execute = AsyncMock(
        return_value=_tool_result(content="Section 43: penalty for damage.", score=None),
    )
    llm_client.generate_structured.return_value = _final_decision("Section 43 covers damage.")

    handle = await _start_handle(execution)
    continuation = _continuation(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
    )

    await continuation.seed_evidence(handle=handle)

    tool_execution_service.execute.assert_awaited_once_with(
        tool_name=TOOL_NAME,
        parameters={
            "query": "What does the supplied evidence establish?",
            "top_k": SEED_RETRIEVAL_TOP_K,
        },
    )
    assert [item.content for item in handle.reasoning_context] == [
        "Section 43: penalty for damage."
    ]
    assert handle.lifecycle.state.tool_call_count == 1

    # The seeded evidence is in the prompt of the first reasoning call.
    await handle.reason()
    sent = llm_client.generate_structured.await_args.kwargs["request"]
    assert any("Section 43: penalty for damage." in m.content for m in sent.messages)


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [NO_RESULTS_CONTENT, RETRIEVAL_FAILED_CONTENT])
async def test_seed_evidence_adds_nothing_when_retrieval_finds_nothing(
    execution: AgentExecution,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
    content: str,
) -> None:
    """
    RetrieverTool reports "nothing found" and "retrieval failed" as
    ordinary successful content; neither is evidence.
    """

    tool_execution_service.execute = AsyncMock(
        return_value=_tool_result(content=content, score=None),
    )

    handle = await _start_handle(execution)

    await _continuation(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
    ).seed_evidence(handle=handle)

    tool_execution_service.execute.assert_awaited_once()
    assert handle.reasoning_context == ()


@pytest.mark.asyncio
async def test_seed_evidence_respects_the_agent_tool_policy(
    agent: LegalAgent,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    registry = AgentRegistry()
    registry.register(component=agent)
    execution = AgentExecution(
        agent_registry=registry,
        retry_policy=__import__(
            "agentic.execution.config",
            fromlist=["ExecutionRetryPolicy"],
        ).ExecutionRetryPolicy(max_attempts=1),
        retry_classifier=RetryClassifier(),
        decision_validator=AgentDecisionValidator(),
        agent_policy_provider=StaticAgentPolicyProvider(
            policies={AGENT_ID: AgentPolicy(agent_id=AGENT_ID, allowed_tools=frozenset())},
        ),
        agent_policy_guard=AgentPolicyGuard(tool_permission_guard=ToolPermissionGuard()),
        tool_registry=ToolRegistry(),
        agent_budget=AgentExecutionBudget(),
    )
    tool_execution_service.execute = AsyncMock()

    handle = await _start_handle(execution)

    await _continuation(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
    ).seed_evidence(handle=handle)

    tool_execution_service.execute.assert_not_awaited()
    assert handle.reasoning_context == ()


@pytest.mark.asyncio
async def test_answer_without_sources_is_replaced_with_no_sources_message(
    execution: AgentExecution,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    """
    The A1 repro case end to end: no evidence, the model answers from its
    own knowledge. One corrective retrieval runs and finds nothing, so the
    answer is replaced -- without asking the model again.
    """

    llm_client.generate_structured.return_value = _final_decision(REJECTED_ANSWER)
    tool_execution_service.execute = AsyncMock(
        return_value=_tool_result(content=NO_RESULTS_CONTENT, score=None),
    )
    answer_evaluator = AsyncMock()
    answer_evaluator.evaluate.side_effect = _no_evidence_evaluation

    handle = await _start_handle(execution)
    initial = await handle.reason()

    result = await asyncio.wait_for(
        _continuation(
            tool_execution_service=tool_execution_service,
            collaboration_bus=collaboration_bus,
            answer_evaluator=answer_evaluator,
        ).execute(handle=handle, initial_result=initial),
        timeout=5,
    )

    assert result.result.termination_reason == TerminationReason.NO_EVIDENCE.value
    assert result.evaluation_summary is not None
    assert result.evaluation_summary.verified is False

    response = AgentResponseMapper(agent_name=AGENT_ID).map(
        state=handle.lifecycle.state,
        execution_id=handle.request.context.execution_id,
        context=handle.reasoning_context,
        evaluation_summary=result.evaluation_summary,
    )

    assert response.content == NO_SOURCES_ANSWER_MESSAGE
    assert REJECTED_ANSWER not in response.content
    assert response.metadata["answer_verified"] is False
    assert response.citations == ()

    tool_execution_service.execute.assert_awaited_once()
    assert answer_evaluator.evaluate.await_count == 1
    assert llm_client.generate_structured.await_count == 1


@pytest.mark.asyncio
async def test_answer_without_sources_is_retried_on_corrective_evidence(
    execution: AgentExecution,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    """
    No evidence at first, but the corrective retrieval finds some: the
    model answers again from it, and that grounded answer is accepted.
    """

    grounded_answer = "Section 43 imposes a penalty for damage to a computer system."
    llm_client.generate_structured.side_effect = [
        _final_decision(REJECTED_ANSWER),
        _final_decision(grounded_answer),
    ]
    tool_execution_service.execute = AsyncMock(
        return_value=_tool_result(content="Section 43: penalty for damage.", score=None),
    )
    answer_evaluator = AsyncMock()
    answer_evaluator.evaluate.side_effect = [
        _no_evidence_evaluation(),
        _grounded_evaluation(),
    ]

    handle = await _start_handle(execution)
    initial = await handle.reason()

    result = await _continuation(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
    ).execute(handle=handle, initial_result=initial)

    assert result.result.decision.final_response == grounded_answer
    assert result.evaluation_summary is not None
    assert result.evaluation_summary.verified is True
    assert handle.lifecycle.state.partial_response == grounded_answer

    # The second evaluation was checked against the retrieved evidence
    # only -- not the gate's own feedback note.
    second_evidence = answer_evaluator.evaluate.await_args_list[1].kwargs["evidence"]
    assert second_evidence == ("Section 43: penalty for damage.",)


@pytest.mark.asyncio
async def test_evaluation_feedback_notes_are_not_evidence(
    execution: AgentExecution,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    """
    The gate's re-ask path adds an "evaluation_feedback" note to
    reasoning_context for the model. The next evaluation must check the
    new answer against the real evidence only, not that note.
    """

    llm_client.generate_structured.side_effect = [
        _final_decision("First answer."),
        _final_decision("Second answer."),
    ]

    # Groundedness and relevance pass, so the first rejection takes the
    # re-ask path (not corrective retrieval), which adds the note.
    answer_evaluator = AsyncMock()
    answer_evaluator.evaluate.side_effect = _grounded_evaluation
    answer_quality_policy = MagicMock()
    answer_quality_policy.is_sufficient.side_effect = [False, True]
    answer_quality_policy.min_groundedness = 0.5
    answer_quality_policy.min_relevance = 0.6
    answer_quality_policy.require_evidence = True

    handle = await _start_handle(
        execution,
        reasoning_context=(_evidence(content="Section 43 covers damage.", score=0.8),),
    )
    initial = await handle.reason()

    result = await _continuation(
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
    ).execute(handle=handle, initial_result=initial)

    assert result.result.decision.final_response == "Second answer."

    notes = [
        item
        for item in handle.reasoning_context
        if item.metadata.get("source_type") == "evaluation_feedback"
    ]
    assert len(notes) == 1, "the re-ask path should have added its note"

    second_evidence = answer_evaluator.evaluate.await_args_list[1].kwargs["evidence"]
    assert second_evidence == ("Section 43 covers damage.",)


@pytest.mark.asyncio
async def test_nothing_found_from_the_models_own_retriever_call_is_not_evidence(
    execution: AgentExecution,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    """
    The model calls the retriever itself and gets "No relevant content
    found.": the model sees that result, but it can't ground an answer.
    With evidence required, the answer ends as the "no sources" answer.
    """

    llm_client.generate_structured.side_effect = [
        _tool_decision(),
        _final_decision(REJECTED_ANSWER),
    ]
    tool_execution_service.execute = AsyncMock(
        return_value=_tool_result(content=NO_RESULTS_CONTENT, score=None),
    )
    answer_evaluator = AsyncMock()
    answer_evaluator.evaluate.side_effect = _no_evidence_evaluation

    handle = await _start_handle(execution)
    initial = await handle.reason()

    result = await asyncio.wait_for(
        _continuation(
            tool_execution_service=tool_execution_service,
            collaboration_bus=collaboration_bus,
            answer_evaluator=answer_evaluator,
        ).execute(handle=handle, initial_result=initial),
        timeout=5,
    )

    # The model's call ran and its result reached the reasoning context...
    assert NO_RESULTS_CONTENT in [item.content for item in handle.reasoning_context]

    # ...but it was not evaluated as evidence.
    first_evidence = answer_evaluator.evaluate.await_args_list[0].kwargs["evidence"]
    assert first_evidence == ()

    assert result.result.termination_reason == TerminationReason.NO_EVIDENCE.value
    assert handle.lifecycle.state.partial_response == NO_SOURCES_ANSWER_MESSAGE

    # The model's own call, then the gate's one corrective retrieval.
    assert tool_execution_service.execute.await_count == 2


# ---------------------------------------------------------------------------
# S5: the runtime can end the execution after the model proposes a FINAL but
# before accepting it (here: the validation-attempt budget). That FINAL's text
# never becomes the response, so it must not be gated, accepted or retried on
# the closed handle. Before the fix, gating it raised "Agent execution handle
# is already closed" (HTTP 500), or -- if it passed -- returned the stale
# response text instead of the answer that was evaluated.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_closed_by_validation_budget_replaces_the_rejected_answer(
    agent: LegalAgent,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    llm_client.generate_structured.side_effect = [
        _final_decision(REJECTED_ANSWER),
        _final_decision("A second answer the runtime never accepts."),
    ]
    tool_execution_service.execute = AsyncMock(
        return_value=_tool_result(content="Section 43 covers damage.", score=0.8),
    )
    answer_evaluator, answer_quality_policy = _yielding_insufficient_answer_evaluator()
    answer_quality_policy.require_evidence = False

    # One retained decision: the corrective retry's new decision is refused.
    execution = _execution_with_budget(agent, max_decisions=1)
    handle = await _start_handle(
        execution,
        reasoning_context=(_evidence(content="Section 43 covers damage.", score=0.8),),
    )
    initial = await handle.reason()

    result = await asyncio.wait_for(
        _continuation(
            tool_execution_service=tool_execution_service,
            collaboration_bus=collaboration_bus,
            answer_evaluator=answer_evaluator,
            answer_quality_policy=answer_quality_policy,
        ).execute(handle=handle, initial_result=initial),
        timeout=5,
    )

    _assert_rejected_answer_replaced(handle, result)
    assert llm_client.generate_structured.await_count == 2
    assert answer_evaluator.evaluate.await_count == 1


@pytest.mark.asyncio
async def test_final_arriving_on_an_ended_execution_is_never_accepted(
    agent: LegalAgent,
    llm_client: object,
    tool_execution_service: ToolExecutionService,
    collaboration_bus,
) -> None:
    """
    The model calls a tool, then proposes a FINAL that the validation
    budget refuses. Even a gate that would accept the answer must not:
    the response would carry text other than the evaluated answer.
    """

    llm_client.generate_structured.side_effect = [
        _tool_decision(),
        _final_decision("An answer the runtime never accepts."),
    ]
    tool_execution_service.execute = AsyncMock(
        return_value=_tool_result(content="Section 43 covers damage.", score=0.8),
    )
    answer_evaluator, answer_quality_policy = _sufficient_answer_evaluator()

    execution = _execution_with_budget(agent, max_decisions=1)
    handle = await _start_handle(execution)
    initial = await handle.reason()

    result = await asyncio.wait_for(
        _continuation(
            tool_execution_service=tool_execution_service,
            collaboration_bus=collaboration_bus,
            answer_evaluator=answer_evaluator,
            answer_quality_policy=answer_quality_policy,
        ).execute(handle=handle, initial_result=initial),
        timeout=5,
    )

    assert result.evaluation_summary is not None
    assert result.evaluation_summary.verified is False
    assert handle.lifecycle.state.partial_response == UNVERIFIED_ANSWER_MESSAGE
    answer_evaluator.evaluate.assert_not_awaited()
