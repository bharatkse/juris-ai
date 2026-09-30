"""
Unit tests for AIOrchestrator.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from agentic.execution.aggregation.response import ResponseAggregator
from agentic.execution.executor import Executor
from agentic.execution.schemas.result import ExecutionResultSchema
from agentic.execution.schemas.state import ExecutionStateSchema, StepExecutionStateSchema
from agentic.execution.validation.response import ResponseValidator
from agentic.guardrails.schemas import GuardrailActionEnum, GuardrailReviewResult
from agentic.orchestration.orchestrator import AIOrchestrator, _stream_slices
from agentic.orchestration.schemas.response import OrchestratorResponse
from core.dto.agent import AgentResponseDTO
from core.dto.approval import ApprovalResponseDTO
from core.dto.planning import ExecutionPlanDTO
from core.dto.response import CitationDTO, SourceDTO
from core.enums import ApprovalStatusEnum, ExecutionModeEnum, ExecutionStatusEnum, IntentEnum
from tests.builders.agentic.orchestrator import build_orchestrator_request


def build_success_execution_result(
    *,
    content: str = "Legal answer.",
    metadata: dict | None = None,
) -> ExecutionResultSchema:
    """
    An execution result shaped like a normal turn that reached FINAL:
    one AgentResponseDTO artifact, no pending action/approval.
    """

    return ExecutionResultSchema(
        state=ExecutionStateSchema(
            request_id=uuid4(),
            status=ExecutionStatusEnum.COMPLETED,
        ),
        artifacts={
            "legal": AgentResponseDTO(
                content=content,
                agent_name="legal",
                metadata=metadata or {},
            ),
        },
        action=None,
        approval=None,
    )


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


def _mock_compliance_log() -> MagicMock:
    compliance_log = MagicMock()
    compliance_log.record_plan_created = AsyncMock()
    compliance_log.record_retrieval_performed = AsyncMock()
    compliance_log.record_tool_call_executed = AsyncMock()
    compliance_log.record_agent_decision = AsyncMock()
    compliance_log.record_guardrail_fired = AsyncMock()
    return compliance_log


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
    authorization.authorize_request = AsyncMock()

    # Never reached by either test below: both exercise paths that
    # return (the no-agent-responses fallback) or raise (the planner
    # blowing up) before the guardrail step -- present only so
    # construction succeeds.
    guardrails = MagicMock()
    guardrails.review = AsyncMock()

    return AIOrchestrator(
        planner=planner,
        executor=executor,
        compliance_log=_mock_compliance_log(),
        # Real validator/aggregator -- this test exists specifically to
        # prove ResponseAggregator.aggregate() is never reached (and
        # its EmptyAggregationError never raised) when there are no
        # agent responses, so both must be the real implementations,
        # not mocks that would hide the bug.
        validator=ResponseValidator(),
        aggregator=ResponseAggregator(),
        authorization=authorization,
        guardrails=guardrails,
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


@pytest.mark.asyncio
async def test_handle_returns_need_input_question_instead_of_generic_fallback(
    orchestrator: AIOrchestrator,
) -> None:
    """
    NEED_INPUT fix: a clarifying-question turn now produces a real
    AgentResponseDTO artifact (AgentResponseMapper runs for NEED_INPUT
    the same way it does for FINAL -- see nodes.py), so agent_responses
    is non-empty and the orchestrator must surface the question as
    real content instead of ever reaching the "no mappable response"
    fallback that test_handle_returns_graceful_fallback_on_non_gated_tool_failure
    exercises for the genuinely-empty case.
    """

    question = "Which jurisdiction applies to this contract?"

    orchestrator._executor.execute = AsyncMock(
        return_value=build_success_execution_result(
            content=question,
            metadata={"termination_reason": "user_input_required"},
        ),
    )
    orchestrator._guardrails.review = AsyncMock(
        return_value=GuardrailReviewResult(
            content=question,
            action=GuardrailActionEnum.NONE,
        ),
    )

    response = await orchestrator.handle(
        request=build_orchestrator_request(),
        action_workflow_service=MagicMock(),
    )

    assert response.content == question
    assert "wasn't able to complete" not in response.content


@pytest.mark.asyncio
async def test_handle_survives_need_input_termination_reason_into_response_metadata(
    orchestrator: AIOrchestrator,
) -> None:
    """
    Not just the question text -- metadata["termination_reason"] set
    by AgentResponseMapper for a NEED_INPUT turn must survive both
    aggregation steps (ResponseAggregator._aggregate_metadata() and
    AIOrchestrator's own OrchestratorResponse construction, which used
    to omit metadata= entirely) and land on the real, aggregated
    OrchestratorResponse -- not just be present at the AgentResponseDTO
    level, where a caller can't see it.
    """

    question = "Which jurisdiction applies to this contract?"

    orchestrator._executor.execute = AsyncMock(
        return_value=build_success_execution_result(
            content=question,
            metadata={"termination_reason": "user_input_required"},
        ),
    )
    orchestrator._guardrails.review = AsyncMock(
        return_value=GuardrailReviewResult(
            content=question,
            action=GuardrailActionEnum.NONE,
        ),
    )

    response = await orchestrator.handle(
        request=build_orchestrator_request(),
        action_workflow_service=MagicMock(),
    )

    assert response.metadata.termination_reason == "user_input_required"


@pytest.mark.asyncio
async def test_handle_logs_accurate_diagnostics_not_a_generic_tool_failure_claim(
    orchestrator: AIOrchestrator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    The fallback log message used to unconditionally claim "(a tool
    call failed)" -- wrong even for the FAILED case it was written
    for whenever the real cause was a policy/validation failure, not a
    tool. It must no longer make that specific claim, and must carry
    the real per-step termination_reason/error so the actual cause is
    diagnosable from the log instead of asserted incorrectly.
    """

    step_id = "step-a"

    orchestrator._executor.execute = AsyncMock(
        return_value=ExecutionResultSchema(
            state=ExecutionStateSchema(
                request_id=uuid4(),
                status=ExecutionStatusEnum.FAILED,
                steps={
                    step_id: StepExecutionStateSchema(
                        step_id=step_id,
                        status=ExecutionStatusEnum.FAILED,
                        error="Delegation to legal is not permitted by policy.",
                        termination_reason="failed_policy",
                    ),
                },
            ),
            artifacts={},
            action=None,
            approval=None,
        ),
    )

    with caplog.at_level("ERROR", logger="agentic.orchestration.orchestrator"):
        response = await orchestrator.handle(
            request=build_orchestrator_request(),
            action_workflow_service=MagicMock(),
        )

    assert "wasn't able to complete" in response.content

    fallback_records = [
        record for record in caplog.records if "mappable agent response" in record.message
    ]
    assert len(fallback_records) == 1

    fallback_record = fallback_records[0]
    assert "tool call failed" not in fallback_record.message
    assert fallback_record.termination_reasons == ("failed_policy",)
    assert fallback_record.step_errors == ("Delegation to legal is not permitted by policy.",)


def _build_orchestrator_for_guardrail_tests(
    *,
    execution_results: list[ExecutionResultSchema],
    guardrail_results: list[GuardrailReviewResult],
) -> AIOrchestrator:
    """
    Build an AIOrchestrator with a real validator/aggregator (the
    guardrail tests care about real aggregated content), a mocked
    executor that returns each of ``execution_results`` in order (one
    call per handle() attempt), and a mocked guardrail service that
    returns each of ``guardrail_results`` in order (one call per
    attempt).
    """

    planner = MagicMock()
    planner.create_plan = AsyncMock(
        return_value=ExecutionPlanDTO(
            intent=IntentEnum.GENERAL,
            mode=ExecutionModeEnum.SEQUENTIAL,
            steps=(),
        )
    )

    executor = MagicMock()
    executor.execute = AsyncMock(side_effect=execution_results)

    authorization = MagicMock()
    authorization.authorize_request = AsyncMock()

    guardrails = MagicMock()
    guardrails.review = AsyncMock(side_effect=guardrail_results)

    return AIOrchestrator(
        planner=planner,
        executor=executor,
        validator=ResponseValidator(),
        aggregator=ResponseAggregator(),
        authorization=authorization,
        guardrails=guardrails,
        compliance_log=_mock_compliance_log(),
        guardrail_max_regenerate_attempts=1,
    )


@pytest.mark.asyncio
async def test_handle_returns_unmodified_content_when_guardrail_clears() -> None:
    """
    A response the guardrail found nothing wrong with is returned as
    generated, with no guardrail info attached.
    """

    orchestrator = _build_orchestrator_for_guardrail_tests(
        execution_results=[build_success_execution_result(content="Clean answer.")],
        guardrail_results=[
            GuardrailReviewResult(
                content="Clean answer.",
                action=GuardrailActionEnum.NONE,
            ),
        ],
    )

    response = await orchestrator.handle(
        request=build_orchestrator_request(),
        action_workflow_service=MagicMock(),
    )

    assert response.content == "Clean answer."
    assert response.guardrail is None
    orchestrator._executor.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_returns_redacted_content_when_guardrail_redacts() -> None:
    """
    A REDACTED verdict returns the guardrail's (redacted) content, not
    the original aggregated content, and reports what fired -- no
    regeneration for a REDACTED (non-BLOCKED) verdict.
    """

    orchestrator = _build_orchestrator_for_guardrail_tests(
        execution_results=[
            build_success_execution_result(content="My PAN is ABCDE1234F."),
        ],
        guardrail_results=[
            GuardrailReviewResult(
                content="My PAN is [REDACTED:IN_PAN].",
                action=GuardrailActionEnum.REDACTED,
                detections=(),
            ),
        ],
    )

    response = await orchestrator.handle(
        request=build_orchestrator_request(),
        action_workflow_service=MagicMock(),
    )

    assert response.content == "My PAN is [REDACTED:IN_PAN]."
    assert response.guardrail is not None
    assert response.guardrail.action == GuardrailActionEnum.REDACTED
    orchestrator._executor.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_regenerates_once_then_succeeds_when_guardrail_blocks() -> None:
    """
    A BLOCKED first attempt triggers exactly one regeneration; a
    clean second attempt is returned normally.
    """

    orchestrator = _build_orchestrator_for_guardrail_tests(
        execution_results=[
            build_success_execution_result(content="Harmful draft."),
            build_success_execution_result(content="Clean retry."),
        ],
        guardrail_results=[
            GuardrailReviewResult(
                content="Harmful draft.",
                action=GuardrailActionEnum.BLOCKED,
            ),
            GuardrailReviewResult(
                content="Clean retry.",
                action=GuardrailActionEnum.NONE,
            ),
        ],
    )

    response = await orchestrator.handle(
        request=build_orchestrator_request(),
        action_workflow_service=MagicMock(),
    )

    assert response.content == "Clean retry."
    assert response.guardrail is None
    assert orchestrator._executor.execute.await_count == 2

    # The regenerate attempt must run on a fresh thread_id, never a
    # replay of the blocked run's thread -- see handle()'s loop.
    first_context = orchestrator._executor.execute.await_args_list[0].kwargs["context"]
    second_context = orchestrator._executor.execute.await_args_list[1].kwargs["context"]
    assert first_context.thread_id != second_context.thread_id


@pytest.mark.asyncio
async def test_handle_returns_fixed_refusal_when_guardrail_blocks_every_attempt() -> None:
    """
    A BLOCKED verdict on every attempt (initial + all regenerate
    attempts) falls back to the fixed refusal message, never a third
    LLM call.
    """

    blocked = GuardrailReviewResult(
        content="Harmful.",
        action=GuardrailActionEnum.BLOCKED,
    )

    orchestrator = _build_orchestrator_for_guardrail_tests(
        execution_results=[
            build_success_execution_result(content="Harmful draft 1."),
            build_success_execution_result(content="Harmful draft 2."),
        ],
        guardrail_results=[blocked, blocked],
    )

    response = await orchestrator.handle(
        request=build_orchestrator_request(),
        action_workflow_service=MagicMock(),
    )

    assert "not able to provide a response" in response.content
    assert response.guardrail is not None
    assert response.guardrail.action == GuardrailActionEnum.BLOCKED
    assert orchestrator._executor.execute.await_count == 2
    assert orchestrator._guardrails.review.await_count == 2


@pytest.mark.asyncio
async def test_handle_records_compliance_log_entries() -> None:
    """
    A normal, clean turn must record PLAN_CREATED (once), AGENT_DECISION
    (once per agent response), and no GUARDRAIL_FIRED row (nothing
    fired) -- the orchestrator-owned half of the compliance trail.
    """

    orchestrator = _build_orchestrator_for_guardrail_tests(
        execution_results=[build_success_execution_result(content="Clean answer.")],
        guardrail_results=[
            GuardrailReviewResult(content="Clean answer.", action=GuardrailActionEnum.NONE),
        ],
    )

    request = build_orchestrator_request()

    await orchestrator.handle(
        request=request,
        action_workflow_service=MagicMock(),
    )

    orchestrator._compliance_log.record_plan_created.assert_awaited_once()
    plan_call = orchestrator._compliance_log.record_plan_created.await_args.kwargs
    assert plan_call["request_id"] == request.request_id
    assert plan_call["user_id"] == str(request.user_id)

    orchestrator._compliance_log.record_agent_decision.assert_awaited_once()
    decision_call = orchestrator._compliance_log.record_agent_decision.await_args.kwargs
    assert decision_call["agent_id"] == "legal"
    assert decision_call["decision_type"] == "final"

    orchestrator._compliance_log.record_guardrail_fired.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_records_an_unverified_answer_in_the_compliance_log() -> None:
    """
    S5: when the answer-quality gate replaced an agent's answer, the
    AGENT_DECISION compliance record carries answer_verified=False and
    the rejected answer's scores.
    """

    execution_result = ExecutionResultSchema(
        state=ExecutionStateSchema(
            request_id=uuid4(),
            status=ExecutionStatusEnum.COMPLETED,
        ),
        artifacts={
            "legal": AgentResponseDTO(
                content="I couldn't verify an answer.",
                agent_name="legal",
                metadata={
                    "groundedness": 0.1,
                    "relevance": 0.2,
                    "answer_verified": False,
                },
            ),
        },
        action=None,
        approval=None,
    )

    orchestrator = _build_orchestrator_for_guardrail_tests(
        execution_results=[execution_result],
        guardrail_results=[
            GuardrailReviewResult(
                content="I couldn't verify an answer.",
                action=GuardrailActionEnum.NONE,
            ),
        ],
    )

    await orchestrator.handle(
        request=build_orchestrator_request(),
        action_workflow_service=MagicMock(),
    )

    decision_call = orchestrator._compliance_log.record_agent_decision.await_args.kwargs
    assert decision_call["answer_verified"] is False
    assert decision_call["groundedness"] == 0.1
    assert decision_call["relevance"] == 0.2


@pytest.mark.asyncio
async def test_handle_records_guardrail_fired_when_redacted() -> None:
    orchestrator = _build_orchestrator_for_guardrail_tests(
        execution_results=[build_success_execution_result(content="My PAN is X.")],
        guardrail_results=[
            GuardrailReviewResult(
                content="My PAN is [REDACTED:IN_PAN].",
                action=GuardrailActionEnum.REDACTED,
            ),
        ],
    )

    await orchestrator.handle(
        request=build_orchestrator_request(),
        action_workflow_service=MagicMock(),
    )

    orchestrator._compliance_log.record_guardrail_fired.assert_awaited_once()
    call = orchestrator._compliance_log.record_guardrail_fired.await_args.kwargs
    assert call["action"] == GuardrailActionEnum.REDACTED.value


@pytest.mark.asyncio
async def test_guardrail_review_receives_real_evidence_text_not_just_citations() -> None:
    """
    OutputGuardrailService.review()'s evidence_text must come from
    AgentResponseDTO.metadata["evidence_text"] (the real, untruncated
    RetrievedContentDTO.content AgentResponseMapper.map() threads
    through -- see mapper.py), not fall back to citation snippets, the
    moment a response actually carries it.
    """

    real_evidence = (
        "Section 2(1)(ta) of the IT Act 2000 defines 'electronic "
        "signature' as authentication of an electronic record by a "
        "subscriber using an electronic technique -- the full "
        "retrieved chunk text, not a 280-char citation snippet."
    )

    orchestrator = _build_orchestrator_for_guardrail_tests(
        execution_results=[
            build_success_execution_result(
                content="Clean answer.",
                metadata={"evidence_text": real_evidence},
            ),
        ],
        guardrail_results=[
            GuardrailReviewResult(content="Clean answer.", action=GuardrailActionEnum.NONE),
        ],
    )

    await orchestrator.handle(
        request=build_orchestrator_request(),
        action_workflow_service=MagicMock(),
    )

    orchestrator._guardrails.review.assert_awaited_once()
    review_call = orchestrator._guardrails.review.await_args.kwargs
    assert review_call["evidence_text"] == real_evidence


@pytest.mark.asyncio
async def test_guardrail_review_falls_back_to_citations_when_no_evidence_text() -> None:
    """
    A response with no metadata["evidence_text"] (e.g. no retrieval
    happened at all) must fall back to the citation-snippet/source-
    title proxy, not send an empty string.
    """

    orchestrator = _build_orchestrator_for_guardrail_tests(
        execution_results=[
            build_success_execution_result(content="Clean answer.", metadata={}),
        ],
        guardrail_results=[
            GuardrailReviewResult(content="Clean answer.", action=GuardrailActionEnum.NONE),
        ],
    )

    await orchestrator.handle(
        request=build_orchestrator_request(),
        action_workflow_service=MagicMock(),
    )

    orchestrator._guardrails.review.assert_awaited_once()
    review_call = orchestrator._guardrails.review.await_args.kwargs
    # No citations/sources on this response either -- the fallback
    # itself resolves to an empty string, not an exception.
    assert review_call["evidence_text"] == ""


# ---------------------------------------------------------------------------
# AIOrchestrator.stream(): streams the guardrail-reviewed text (S2).
# ---------------------------------------------------------------------------


def _build_streaming_orchestrator_for_guardrail_tests(
    *,
    execution_results: list[ExecutionResultSchema],
    guardrail_results: list[GuardrailReviewResult],
) -> AIOrchestrator:
    """
    Same as _build_orchestrator_for_guardrail_tests() above, but the
    executor is spec'd to the real Executor, so stream() can only use
    what exists there (execute(), no second streaming path).
    """

    orchestrator = _build_orchestrator_for_guardrail_tests(
        execution_results=execution_results,
        guardrail_results=guardrail_results,
    )

    executor = MagicMock(spec=Executor)
    executor.execute = AsyncMock(side_effect=execution_results)
    orchestrator._executor = executor

    return orchestrator


async def _collect_stream(orchestrator: AIOrchestrator) -> list:
    return [
        item
        async for item in orchestrator.stream(
            request=build_orchestrator_request(),
            action_workflow_service=MagicMock(),
        )
    ]


def test_stream_slices_rejoin_to_the_exact_text_and_never_split_words() -> None:
    text = "  Section 43 of the IT Act 2000 imposes penalty and compensation\nfor damage to computer systems.  "

    slices = list(_stream_slices(text))

    assert "".join(slices) == text
    assert len(slices) > 1
    words = text.split()
    for text_slice in slices:
        for word in text_slice.split():
            assert word in words


def test_stream_slices_of_empty_text_is_empty() -> None:
    assert list(_stream_slices("")) == []


@pytest.mark.asyncio
async def test_stream_sends_exactly_the_reviewed_text_when_guardrail_clears() -> None:
    """
    S2 regression: the streamed text is the text the guardrails
    reviewed (and ChatService persists), sliced; one empty terminal
    chunk carries the full OrchestratorResponse. Before the fix the
    stream replayed a separate second generation.
    """

    reviewed = (
        "Section 43 of the IT Act 2000 imposes penalty and compensation "
        "for damage to a computer, computer system or network."
    )

    orchestrator = _build_streaming_orchestrator_for_guardrail_tests(
        execution_results=[build_success_execution_result(content=reviewed)],
        guardrail_results=[
            GuardrailReviewResult(content=reviewed, action=GuardrailActionEnum.NONE),
        ],
    )

    received = await _collect_stream(orchestrator)

    body, terminal = received[:-1], received[-1]

    assert len(body) > 1
    assert "".join(item.content for item in body) == reviewed
    assert all(not item.is_final and item.response is None for item in body)

    assert terminal.is_final is True
    assert terminal.content == ""
    assert terminal.response is not None
    assert terminal.response.content == reviewed
    assert terminal.response.guardrail is None

    orchestrator._executor.execute.assert_awaited_once()
    orchestrator._guardrails.review.assert_awaited_once()
    assert orchestrator._guardrails.review.await_args.kwargs["content"] == reviewed


@pytest.mark.asyncio
async def test_stream_emits_only_the_fallback_chunk_when_guardrail_blocks_every_attempt() -> None:
    """
    Guardrail-blocked, every attempt: only the fixed refusal reaches
    the caller, as a single terminal chunk.
    """

    blocked = GuardrailReviewResult(content="Harmful.", action=GuardrailActionEnum.BLOCKED)

    orchestrator = _build_streaming_orchestrator_for_guardrail_tests(
        execution_results=[
            build_success_execution_result(content="Harmful draft 1."),
            build_success_execution_result(content="Harmful draft 2."),
        ],
        guardrail_results=[blocked, blocked],
    )

    received = await _collect_stream(orchestrator)

    assert len(received) == 1

    only_chunk = received[0]
    assert only_chunk.is_final is True
    assert "not able to provide a response" in only_chunk.content
    assert only_chunk.response is not None
    assert only_chunk.response.guardrail is not None
    assert only_chunk.response.guardrail.action == GuardrailActionEnum.BLOCKED

    all_content = " ".join(item.content for item in received)
    assert "Harmful draft 1." not in all_content
    assert "Harmful draft 2." not in all_content

    assert orchestrator._executor.execute.await_count == 2


@pytest.mark.asyncio
async def test_stream_sends_only_the_redacted_text_never_the_raw_pii() -> None:
    """
    REDACTED: the stream carries the redacted text, never the
    pre-redaction answer.
    """

    orchestrator = _build_streaming_orchestrator_for_guardrail_tests(
        execution_results=[build_success_execution_result(content="My PAN is ABCDE1234F.")],
        guardrail_results=[
            GuardrailReviewResult(
                content="My PAN is [REDACTED:IN_PAN].",
                action=GuardrailActionEnum.REDACTED,
            ),
        ],
    )

    received = await _collect_stream(orchestrator)

    terminal = received[-1]
    assert terminal.is_final is True
    assert terminal.content == ""
    assert terminal.response is not None
    assert terminal.response.content == "My PAN is [REDACTED:IN_PAN]."
    assert terminal.response.guardrail is not None
    assert terminal.response.guardrail.action == GuardrailActionEnum.REDACTED

    assert "".join(item.content for item in received) == "My PAN is [REDACTED:IN_PAN]."
    assert all("ABCDE1234F" not in item.content for item in received)


@pytest.mark.asyncio
async def test_stream_terminal_chunk_matches_handle_for_the_same_inputs() -> None:
    """
    (d) Parity: usage/citations/sources/content on stream()'s terminal
    chunk must exactly match what handle() produces for equivalent
    agent responses -- both call the exact same aggregate() with the
    same inputs, not a second, parallel computation. (Usage comes from
    the LLM calls made, none here; see the usage tests.)
    """

    def _agent_response() -> AgentResponseDTO:
        return AgentResponseDTO(
            content="Section 43 imposes penalty and compensation for damage.",
            agent_name="legal",
            citations=(CitationDTO(title="IT Act 2000", source="it-act-2000", reference="s.43"),),
            sources=(
                SourceDTO(title="Information Technology Act, 2000", uri="https://example.test"),
            ),
        )

    def _execution_result() -> ExecutionResultSchema:
        return ExecutionResultSchema(
            state=ExecutionStateSchema(
                request_id=uuid4(),
                status=ExecutionStatusEnum.COMPLETED,
            ),
            artifacts={"legal": _agent_response()},
            action=None,
            approval=None,
        )

    clean = GuardrailReviewResult(
        content="Section 43 imposes penalty and compensation for damage.",
        action=GuardrailActionEnum.NONE,
    )

    handle_orchestrator = _build_orchestrator_for_guardrail_tests(
        execution_results=[_execution_result()],
        guardrail_results=[clean],
    )

    handle_response = await handle_orchestrator.handle(
        request=build_orchestrator_request(),
        action_workflow_service=MagicMock(),
    )

    stream_orchestrator = _build_streaming_orchestrator_for_guardrail_tests(
        execution_results=[_execution_result()],
        guardrail_results=[clean],
    )

    received = [
        item
        async for item in stream_orchestrator.stream(
            request=build_orchestrator_request(),
            action_workflow_service=MagicMock(),
        )
    ]

    stream_response = received[-1].response

    assert stream_response is not None
    assert stream_response.content == handle_response.content
    assert stream_response.usage == handle_response.usage
    assert stream_response.citations == handle_response.citations
    assert stream_response.sources == handle_response.sources


@pytest.mark.asyncio
async def test_handle_refuses_when_harmful_content_check_cannot_run() -> None:
    """
    With the real guardrail service and judge, a judge LLM call that
    fails on every attempt must yield the fixed refusal -- never the
    unchecked answer, and never an exception (500).
    """

    from agentic.guardrails.harmful_content import HarmfulContentJudge
    from agentic.guardrails.service import OutputGuardrailService

    async def failing_judge(prompt: str) -> str:
        raise RuntimeError("judge provider unavailable")

    orchestrator = _build_orchestrator_for_guardrail_tests(
        execution_results=[
            build_success_execution_result(content="Unchecked answer 1."),
            build_success_execution_result(content="Unchecked answer 2."),
        ],
        guardrail_results=[],
    )
    orchestrator._guardrails = OutputGuardrailService(
        pii_detector=MagicMock(),
        harmful_content_judge=HarmfulContentJudge(judge=failing_judge),
    )

    response = await orchestrator.handle(
        request=build_orchestrator_request(),
        action_workflow_service=MagicMock(),
    )

    assert "not able to provide a response" in response.content
    assert "Unchecked answer" not in response.content
    assert response.guardrail is not None
    assert response.guardrail.action == GuardrailActionEnum.BLOCKED
    assert orchestrator._executor.execute.await_count == 2


# ---------------------------------------------------------------------------
# A turn paused for approval (A6): the user is told it's waiting for their
# approval, not that "something went wrong".
# ---------------------------------------------------------------------------


def build_paused_execution_result() -> ExecutionResultSchema:
    """
    A single-step turn paused on a gated call: no FINAL artifact, status
    WAITING_FOR_APPROVAL, and the pending approval attached.
    """

    now = datetime.now(UTC)

    return ExecutionResultSchema(
        state=ExecutionStateSchema(
            request_id=uuid4(),
            status=ExecutionStatusEnum.WAITING_FOR_APPROVAL,
        ),
        artifacts={},
        action=None,
        approval=ApprovalResponseDTO(
            approval_id="appr_" + "a" * 32,
            agent_action_id="actn_" + "b" * 32,
            requested_by="user_" + "c" * 32,
            approved_by=None,
            status=ApprovalStatusEnum.WAITING,
            decision_type=None,
            decision_reason=None,
            edited_payload=None,
            edited_fingerprint=None,
            expires_at=now + timedelta(minutes=15),
            created_at=now,
            decided_at=None,
        ),
    )


PENDING_APPROVAL_TEXT = "needs your approval"


@pytest.mark.asyncio
async def test_handle_reports_a_pending_approval_not_an_error(
    orchestrator: AIOrchestrator,
) -> None:
    orchestrator._executor.execute = AsyncMock(return_value=build_paused_execution_result())

    response = await orchestrator.handle(
        request=build_orchestrator_request(),
        action_workflow_service=MagicMock(),
    )

    assert PENDING_APPROVAL_TEXT in response.content
    assert "went wrong" not in response.content
    assert response.approval is not None
    assert response.approval.approval_id == "appr_" + "a" * 32


@pytest.mark.asyncio
async def test_stream_reports_a_pending_approval_not_an_error(
    orchestrator: AIOrchestrator,
) -> None:
    orchestrator._executor.execute = AsyncMock(return_value=build_paused_execution_result())

    items = [
        item
        async for item in orchestrator.stream(
            request=build_orchestrator_request(),
            action_workflow_service=MagicMock(),
        )
    ]

    final = items[-1]
    assert final.is_final is True
    assert PENDING_APPROVAL_TEXT in final.response.content
    assert "went wrong" not in final.response.content
    assert final.response.approval is not None


@pytest.mark.asyncio
async def test_resume_that_pauses_again_reports_the_new_pending_approval(
    orchestrator: AIOrchestrator,
) -> None:
    """
    An approved call whose resumed turn proposes another gated call used
    to be reported as "it failed after approval".
    """

    orchestrator._executor.resume = AsyncMock(return_value=build_paused_execution_result())

    response = await orchestrator.resume(
        thread_id="thread-1",
        user_id="user_" + "c" * 32,
        conversation_id="conv_" + "d" * 32,
        plan=MagicMock(),
        approved=True,
        tool_result=None,
        action_workflow_service=MagicMock(),
    )

    assert PENDING_APPROVAL_TEXT in response.content
    assert "failed" not in response.content
    assert response.approval is not None


@pytest.mark.asyncio
async def test_resume_after_rejection_still_says_not_approved(
    orchestrator: AIOrchestrator,
) -> None:
    orchestrator._executor.resume = AsyncMock(return_value=build_failed_execution_result())

    response = await orchestrator.resume(
        thread_id="thread-1",
        user_id="user_" + "c" * 32,
        conversation_id="conv_" + "d" * 32,
        plan=MagicMock(),
        approved=False,
        tool_result=None,
        action_workflow_service=MagicMock(),
    )

    assert "not approved" in response.content


# ---------------------------------------------------------------------------
# R3: a turn's usage is every LLM call it made
# ---------------------------------------------------------------------------


def _calls_llm(prompt_tokens: int, completion_tokens: int, result=None):
    """An async stand-in for a stage that makes one LLM call."""

    from core.usage import record_llm_usage

    async def stage(*_args, **_kwargs):
        record_llm_usage(
            provider="groq",
            model="gpt-oss",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
        return result

    return stage


def _usage_orchestrator() -> AIOrchestrator:
    """Planner, executor and guardrail judge each make one LLM call."""

    orchestrator = _build_streaming_orchestrator_for_guardrail_tests(
        execution_results=[],
        guardrail_results=[],
    )
    orchestrator._planner.create_plan = _calls_llm(
        100,
        20,
        ExecutionPlanDTO(intent=IntentEnum.GENERAL, mode=ExecutionModeEnum.SEQUENTIAL, steps=()),
    )
    orchestrator._executor.execute = _calls_llm(
        300, 50, build_success_execution_result(content="Answer.")
    )
    orchestrator._guardrails.review = _calls_llm(
        10, 1, GuardrailReviewResult(content="Answer.", action=GuardrailActionEnum.NONE)
    )
    return orchestrator


@pytest.mark.asyncio
async def test_handle_reports_the_usage_of_every_llm_call_in_the_turn() -> None:
    """
    Before R3 the response's usage was summed from AgentResponseDTO.usage,
    which nothing set: always zero, so the daily token quota never moved.
    """

    response = await _usage_orchestrator().handle(
        request=build_orchestrator_request(),
        action_workflow_service=MagicMock(),
    )

    assert response.usage.prompt_tokens == 410
    assert response.usage.completion_tokens == 71
    assert response.usage.total_tokens == 481
    assert (response.usage.provider, response.usage.model) == ("groq", "gpt-oss")


@pytest.mark.asyncio
async def test_stream_reports_the_same_usage_on_its_final_chunk() -> None:
    items = await _collect_stream(_usage_orchestrator())

    final = items[-1]
    assert final.is_final is True
    assert final.response.usage.total_tokens == 481
    assert all(item.response is None for item in items[:-1])


@pytest.mark.asyncio
async def test_resume_reports_the_usage_of_the_resumed_turn(
    orchestrator: AIOrchestrator,
) -> None:
    orchestrator._executor.resume = _calls_llm(200, 40, build_failed_execution_result())

    response = await orchestrator.resume(
        thread_id="thread-1",
        user_id="user_" + "c" * 32,
        conversation_id="conv_" + "d" * 32,
        plan=MagicMock(),
        approved=False,
        tool_result=None,
        action_workflow_service=MagicMock(),
    )

    assert response.usage.total_tokens == 240


@pytest.mark.asyncio
async def test_each_turn_counts_only_its_own_calls() -> None:
    orchestrator = _usage_orchestrator()

    first = await orchestrator.handle(
        request=build_orchestrator_request(),
        action_workflow_service=MagicMock(),
    )
    second = await orchestrator.handle(
        request=build_orchestrator_request(),
        action_workflow_service=MagicMock(),
    )

    assert first.usage.total_tokens == second.usage.total_tokens == 481


# ---------------------------------------------------------------------------
# R3: the per-request token quota ends the request, whoever caught it
# ---------------------------------------------------------------------------


def _refused_and_swallowed(result):
    """
    A stage whose LLM call the quota refuses, and which turns the refusal
    into a normal result -- as the agent runtime turns any LLM failure
    into a FAILED step.
    """

    from core.exceptions.rate_limit import RequestTokenQuotaExceededError
    from core.usage import check_request_token_quota

    async def stage(*_args, **_kwargs):
        try:
            check_request_token_quota(["word " * 2_000])
        except RequestTokenQuotaExceededError:
            return result
        raise AssertionError("the quota should have refused this call")

    return stage


def _quota_orchestrator() -> AIOrchestrator:
    orchestrator = _usage_orchestrator()
    orchestrator._executor.execute = _refused_and_swallowed(build_failed_execution_result())
    return orchestrator


@pytest.mark.asyncio
async def test_handle_raises_the_quota_refusal_even_if_a_stage_swallowed_it() -> None:
    from core.exceptions.rate_limit import RequestTokenQuotaExceededError
    from core.usage import request_token_quota

    with request_token_quota(500), pytest.raises(RequestTokenQuotaExceededError) as raised:
        await _quota_orchestrator().handle(
            request=build_orchestrator_request(),
            action_workflow_service=MagicMock(),
        )

    error = raised.value
    assert error.quota == 500
    # The planner's call (100 + 20) was made before the refusal and is
    # carried, so it can still be recorded.
    assert error.used == 120
    assert error.prompt_tokens >= 100
    assert error.completion_tokens >= 20


@pytest.mark.asyncio
async def test_stream_raises_the_quota_refusal_before_sending_an_answer() -> None:
    from core.exceptions.rate_limit import RequestTokenQuotaExceededError
    from core.usage import request_token_quota

    sent = []

    with request_token_quota(500), pytest.raises(RequestTokenQuotaExceededError):
        async for chunk in _quota_orchestrator().stream(
            request=build_orchestrator_request(),
            action_workflow_service=MagicMock(),
        ):
            sent.append(chunk)

    assert sent == []


def _checks_then_calls_llm(prompt_tokens: int, completion_tokens: int, result=None):
    """A stage whose one LLM call is checked against the quota first, as
    LLMClient.generate() does."""

    from core.usage import check_request_token_quota

    record = _calls_llm(prompt_tokens, completion_tokens, result)

    async def stage(*args, **kwargs):
        check_request_token_quota(["x" * prompt_tokens])
        return await record(*args, **kwargs)

    return stage


def _checked_usage_orchestrator(monkeypatch: pytest.MonkeyPatch) -> AIOrchestrator:
    """
    _usage_orchestrator(), each call checked first, one token per prompt
    character. Before each call: planner 0 + 100, executor 120 + 300,
    judge 470 + 10; the turn uses 481.
    """

    monkeypatch.setattr("agentic.orchestration.orchestrator.estimate_tokens", len)

    orchestrator = _usage_orchestrator()
    orchestrator._planner.create_plan = _checks_then_calls_llm(
        100,
        20,
        ExecutionPlanDTO(intent=IntentEnum.GENERAL, mode=ExecutionModeEnum.SEQUENTIAL, steps=()),
    )
    orchestrator._executor.execute = _checks_then_calls_llm(
        300, 50, build_success_execution_result(content="Answer.")
    )
    orchestrator._guardrails.review = _checks_then_calls_llm(
        10, 1, GuardrailReviewResult(content="Answer.", action=GuardrailActionEnum.NONE)
    )
    return orchestrator


@pytest.mark.asyncio
async def test_a_turn_whose_every_call_fits_the_quota_is_answered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.usage import request_token_quota

    with request_token_quota(480):  # the judge's call: 470 + 10 = 480
        response = await _checked_usage_orchestrator(monkeypatch).handle(
            request=build_orchestrator_request(),
            action_workflow_service=MagicMock(),
        )

    assert response.content == "Answer."
    # The last call's output may take the total past the quota (only the
    # prompt is known before a call), as with the daily quota.
    assert response.usage.total_tokens == 481


@pytest.mark.asyncio
async def test_one_token_less_refuses_the_last_call(monkeypatch: pytest.MonkeyPatch) -> None:
    from core.exceptions.rate_limit import RequestTokenQuotaExceededError
    from core.usage import request_token_quota

    orchestrator = _checked_usage_orchestrator(monkeypatch)

    with request_token_quota(479), pytest.raises(RequestTokenQuotaExceededError) as raised:
        await orchestrator.handle(
            request=build_orchestrator_request(),
            action_workflow_service=MagicMock(),
        )

    assert (raised.value.used, raised.value.requested) == (470, 10)
    assert (raised.value.prompt_tokens, raised.value.completion_tokens) == (400, 70)


@pytest.mark.asyncio
async def test_a_resumed_turn_is_not_capped(orchestrator: AIOrchestrator) -> None:
    """Only ChatService sets a quota; HitlResumeService doesn't."""

    from core.usage import check_request_token_quota

    async def resume(*_args, **_kwargs):
        check_request_token_quota(["word " * 50_000])
        return build_failed_execution_result()

    orchestrator._executor.resume = resume

    response = await orchestrator.resume(
        thread_id="thread-1",
        user_id="user_" + "c" * 32,
        conversation_id="conv_" + "d" * 32,
        plan=MagicMock(),
        approved=False,
        tool_result=None,
        action_workflow_service=MagicMock(),
    )

    assert "not approved" in response.content


# ---------------------------------------------------------------------------
# A7: a plan over the step limit gets a reply, not an error or a cut plan
# ---------------------------------------------------------------------------


def _plan_too_large_orchestrator() -> AIOrchestrator:
    from core.exceptions.planning import PlanTooLargeError

    orchestrator = _build_streaming_orchestrator_for_guardrail_tests(
        execution_results=[],
        guardrail_results=[],
    )
    orchestrator._planner.create_plan = AsyncMock(
        side_effect=PlanTooLargeError(step_count=9, max_steps=6)
    )
    return orchestrator


@pytest.mark.asyncio
async def test_handle_answers_a_plan_over_the_step_limit_without_running_it() -> None:
    orchestrator = _plan_too_large_orchestrator()

    response = await orchestrator.handle(
        request=build_orchestrator_request(),
        action_workflow_service=MagicMock(),
    )

    assert response.content == (
        "This request would need 9 steps, but I can run at most 6 in one turn. "
        "Please split it into smaller questions."
    )
    assert response.approval is None
    orchestrator._executor.execute.assert_not_awaited()
    orchestrator._guardrails.review.assert_not_awaited()


@pytest.mark.asyncio
async def test_stream_answers_a_plan_over_the_step_limit_in_one_final_chunk() -> None:
    orchestrator = _plan_too_large_orchestrator()

    items = await _collect_stream(orchestrator)

    assert len(items) == 1
    assert items[0].is_final is True
    assert "at most 6 in one turn" in items[0].response.content
    orchestrator._executor.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_other_plan_validation_errors_still_fail_the_request() -> None:
    from core.exceptions.planning import PlanValidationError

    orchestrator = _plan_too_large_orchestrator()
    orchestrator._planner.create_plan = AsyncMock(side_effect=PlanValidationError("cycle"))

    with pytest.raises(PlanValidationError):
        await orchestrator.handle(
            request=build_orchestrator_request(),
            action_workflow_service=MagicMock(),
        )


def _orchestrator_with_deadline_probes(seen: dict[str, float | None]) -> AIOrchestrator:
    """Planning takes 0.2 s; both stages record the deadline they run under."""

    from core.deadline import remaining_seconds

    async def create_plan(**_kwargs):
        seen["planning"] = remaining_seconds()
        await asyncio.sleep(0.2)
        return ExecutionPlanDTO(
            intent=IntentEnum.GENERAL, mode=ExecutionModeEnum.SEQUENTIAL, steps=()
        )

    async def execute(**_kwargs):
        seen["execution"] = remaining_seconds()
        return build_failed_execution_result()

    planner = MagicMock()
    planner.create_plan = create_plan
    executor = MagicMock()
    executor.execute = execute
    authorization = MagicMock()
    authorization.authorize_request = AsyncMock()

    return AIOrchestrator(
        planner=planner,
        executor=executor,
        compliance_log=_mock_compliance_log(),
        validator=ResponseValidator(),
        aggregator=ResponseAggregator(),
        authorization=authorization,
        guardrails=MagicMock(),
        request_timeout_seconds=5.0,
    )


@pytest.mark.asyncio
async def test_a_deadline_opened_by_the_caller_bounds_the_whole_turn() -> None:
    """
    G1: ChatService opens request_deadline() before summarizing; the
    turn's own deadline inside it can't extend it (the earlier one wins).
    """

    import asyncio

    from core.deadline import remaining_seconds

    seen: dict[str, float | None] = {}
    orchestrator = _orchestrator_with_deadline_probes(seen)

    with orchestrator.request_deadline():
        assert remaining_seconds() is not None
        await asyncio.sleep(0.3)  # summarization
        await orchestrator.handle(
            request=build_orchestrator_request(),
            action_workflow_service=MagicMock(),
        )

    assert seen["planning"] is not None and seen["planning"] <= 5.0 - 0.3
    assert remaining_seconds() is None


@pytest.mark.asyncio
async def test_the_request_deadline_covers_planning() -> None:
    """
    R18: the deadline starts before planning, so the planner's call sees it
    (and FailoverLLMClient's check applies), and planning time is taken out
    of what execution gets.
    """

    seen: dict[str, float | None] = {}
    orchestrator = _orchestrator_with_deadline_probes(seen)

    await orchestrator.handle(
        request=build_orchestrator_request(),
        action_workflow_service=MagicMock(),
    )

    assert seen["planning"] is not None and seen["planning"] <= 5.0
    assert seen["execution"] is not None and seen["execution"] <= 5.0 - 0.2


@pytest.mark.asyncio
async def test_the_request_deadline_covers_planning_when_streaming() -> None:
    seen: dict[str, float | None] = {}
    orchestrator = _orchestrator_with_deadline_probes(seen)

    async for _ in orchestrator.stream(
        request=build_orchestrator_request(),
        action_workflow_service=MagicMock(),
    ):
        pass

    assert seen["planning"] is not None and seen["planning"] <= 5.0
    assert seen["execution"] is not None and seen["execution"] <= 5.0 - 0.2
