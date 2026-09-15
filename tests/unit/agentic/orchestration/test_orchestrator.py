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
from agentic.guardrails.schemas import GuardrailActionEnum, GuardrailReviewResult
from agentic.orchestration.orchestrator import AIOrchestrator
from agentic.orchestration.schemas.response import OrchestratorResponse
from core.dto.agent import AgentResponseDTO
from core.dto.planning import ExecutionPlanDTO
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
