"""
Unit tests for AIOrchestrator.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from agentic.execution.aggregation.response import ResponseAggregator
from agentic.execution.schemas.result import ExecutionResultSchema
from agentic.execution.schemas.state import ExecutionStateSchema, StepExecutionStateSchema
from agentic.execution.validation.response import ResponseValidator
from agentic.guardrails.schemas import GuardrailActionEnum, GuardrailReviewResult
from agentic.orchestration.orchestrator import AIOrchestrator
from agentic.orchestration.schemas.response import OrchestratorResponse
from core.dto.agent import AgentResponseDTO, AgentStreamChunkDTO
from core.dto.planning import ExecutionPlanDTO
from core.dto.response import CitationDTO, SourceDTO, UsageDTO
from core.enums import ExecutionModeEnum, ExecutionStatusEnum, IntentEnum
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
    authorization.authorize_request = MagicMock()

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
    authorization.authorize_request = MagicMock()

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
# Phase 4 of the /chat/stream plan: AIOrchestrator.stream().
# ---------------------------------------------------------------------------


async def _stream_attempt(
    chunks: list[AgentStreamChunkDTO],
    execution_result: ExecutionResultSchema,
):
    """
    One regenerate-loop attempt's worth of Executor.execute_streaming()
    output -- chunks, then the ExecutionResultSchema, matching
    ExecutionSession.execute_streaming()'s real shape.
    """

    for chunk in chunks:
        yield chunk

    yield execution_result


def _build_streaming_orchestrator_for_guardrail_tests(
    *,
    attempts: list[tuple[list[AgentStreamChunkDTO], ExecutionResultSchema]],
    guardrail_results: list[GuardrailReviewResult],
    guardrail_max_regenerate_attempts: int = 1,
) -> AIOrchestrator:
    """
    Streaming counterpart to _build_orchestrator_for_guardrail_tests()
    above: a mocked executor.execute_streaming returning one fresh
    async generator per regenerate-loop attempt (in order), everything
    else identical.
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
    executor.execute_streaming = MagicMock(
        side_effect=[
            _stream_attempt(chunks, execution_result) for chunks, execution_result in attempts
        ],
    )

    authorization = MagicMock()
    authorization.authorize_request = MagicMock()

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
        guardrail_max_regenerate_attempts=guardrail_max_regenerate_attempts,
    )


@pytest.mark.asyncio
async def test_stream_replays_buffered_chunks_then_emits_final_response_when_guardrail_clears() -> (
    None
):
    """
    (a) Normal stream-through-to-final: a NONE verdict replays the
    buffered chunks verbatim, then one empty terminal chunk carries
    the full OrchestratorResponse.
    """

    chunks = [
        AgentStreamChunkDTO(content="Sec", is_final=False),
        AgentStreamChunkDTO(content="tion 43.", is_final=True, finish_reason="stop"),
    ]

    orchestrator = _build_streaming_orchestrator_for_guardrail_tests(
        attempts=[
            (chunks, build_success_execution_result(content="Section 43.")),
        ],
        guardrail_results=[
            GuardrailReviewResult(content="Section 43.", action=GuardrailActionEnum.NONE),
        ],
    )

    received = [
        item
        async for item in orchestrator.stream(
            request=build_orchestrator_request(),
            action_workflow_service=MagicMock(),
        )
    ]

    assert len(received) == 3

    assert [item.content for item in received[:2]] == ["Sec", "tion 43."]
    assert all(not item.is_final for item in received[:2])
    assert all(item.response is None for item in received[:2])

    terminal = received[-1]
    assert terminal.is_final is True
    assert terminal.content == ""
    assert terminal.response is not None
    assert terminal.response.content == "Section 43."
    assert terminal.response.guardrail is None

    orchestrator._executor.execute_streaming.assert_called_once()


@pytest.mark.asyncio
async def test_stream_emits_only_the_fallback_chunk_when_guardrail_blocks_every_attempt() -> None:
    """
    (b) Guardrail-blocked, every attempt: only the fixed refusal
    reaches the caller, as a single terminal chunk -- zero partial
    content from either blocked draft leaked anywhere in the stream.
    """

    blocked = GuardrailReviewResult(content="Harmful.", action=GuardrailActionEnum.BLOCKED)

    orchestrator = _build_streaming_orchestrator_for_guardrail_tests(
        attempts=[
            (
                [AgentStreamChunkDTO(content="Harmful draft 1.", is_final=True)],
                build_success_execution_result(content="Harmful draft 1."),
            ),
            (
                [AgentStreamChunkDTO(content="Harmful draft 2.", is_final=True)],
                build_success_execution_result(content="Harmful draft 2."),
            ),
        ],
        guardrail_results=[blocked, blocked],
    )

    received = [
        item
        async for item in orchestrator.stream(
            request=build_orchestrator_request(),
            action_workflow_service=MagicMock(),
        )
    ]

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

    assert orchestrator._executor.execute_streaming.call_count == 2


@pytest.mark.asyncio
async def test_stream_emits_only_the_redacted_chunk_never_the_raw_pii_chunks() -> None:
    """
    (c) Guardrail-redacted -- the specific bug this investigation
    found: REDACTED content differs from what was actually streamed
    during generation. The raw, pre-redaction chunks must never reach
    the caller -- only the redacted content, as a single terminal
    chunk. Not covered incidentally by the BLOCKED test above: BLOCKED
    discards content entirely, but REDACTED's whole point is that
    content DOES reach the caller, just not the version that was
    buffered.
    """

    raw_chunks = [
        AgentStreamChunkDTO(content="My PAN is ", is_final=False),
        AgentStreamChunkDTO(content="ABCDE1234F.", is_final=True),
    ]

    orchestrator = _build_streaming_orchestrator_for_guardrail_tests(
        attempts=[
            (raw_chunks, build_success_execution_result(content="My PAN is ABCDE1234F.")),
        ],
        guardrail_results=[
            GuardrailReviewResult(
                content="My PAN is [REDACTED:IN_PAN].",
                action=GuardrailActionEnum.REDACTED,
            ),
        ],
    )

    received = [
        item
        async for item in orchestrator.stream(
            request=build_orchestrator_request(),
            action_workflow_service=MagicMock(),
        )
    ]

    assert len(received) == 1

    only_chunk = received[0]
    assert only_chunk.is_final is True
    assert only_chunk.content == "My PAN is [REDACTED:IN_PAN]."
    assert only_chunk.response is not None
    assert only_chunk.response.content == "My PAN is [REDACTED:IN_PAN]."
    assert only_chunk.response.guardrail is not None
    assert only_chunk.response.guardrail.action == GuardrailActionEnum.REDACTED

    all_content = " ".join(item.content for item in received)
    assert "ABCDE1234F" not in all_content


@pytest.mark.asyncio
async def test_stream_terminal_chunk_matches_handle_for_the_same_inputs() -> None:
    """
    (d) Parity: usage/citations/sources/content on stream()'s terminal
    chunk must exactly match what handle() produces for equivalent
    agent responses -- both call the exact same aggregate() with the
    same inputs, not a second, parallel computation.
    """

    def _agent_response() -> AgentResponseDTO:
        return AgentResponseDTO(
            content="Section 43 imposes penalty and compensation for damage.",
            agent_name="legal",
            citations=(CitationDTO(title="IT Act 2000", source="it-act-2000", reference="s.43"),),
            sources=(
                SourceDTO(title="Information Technology Act, 2000", uri="https://example.test"),
            ),
            usage=UsageDTO(
                provider="groq",
                model="llama-3.3-70b",
                prompt_tokens=120,
                completion_tokens=45,
                total_tokens=165,
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
        attempts=[
            (
                [
                    AgentStreamChunkDTO(
                        content="Section 43 imposes penalty and compensation for damage.",
                        is_final=True,
                    ),
                ],
                _execution_result(),
            ),
        ],
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
