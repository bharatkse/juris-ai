"""
Unit tests for AgentResponseMapper.
"""

from __future__ import annotations

from datetime import UTC, datetime

from agentic.agents.runtime.lifecycle.budget import AgentExecutionBudget
from agentic.agents.runtime.lifecycle.state import AgentState
from agentic.agents.runtime.lifecycle.termination import AgentExecutionStatus
from agentic.evaluation.answer import AnswerEvaluationSummary
from agentic.execution.aggregation.mapper import AgentResponseMapper
from core.dto.tool import RetrievedContentDTO
from core.enums import RetrievalSourceEnum


def _state(*, partial_response: str = "Answer.") -> AgentState:
    return AgentState(
        budget=AgentExecutionBudget(),
        started_at=datetime.now(UTC),
        status=AgentExecutionStatus.COMPLETED,
        partial_response=partial_response,
    )


def test_map_populates_evidence_text_from_reasoning_context() -> None:
    context = (
        RetrievedContentDTO(
            source=RetrievalSourceEnum.DOCUMENT,
            source_name="statute",
            content="First retrieved chunk.",
            score=0.9,
        ),
        RetrievedContentDTO(
            source=RetrievalSourceEnum.DOCUMENT,
            source_name="case-law",
            content="Second retrieved chunk.",
            score=0.8,
        ),
    )

    mapper = AgentResponseMapper(agent_name="legal")
    response = mapper.map(
        state=_state(),
        execution_id="exec-1",
        context=context,
    )

    assert response.metadata["evidence_text"] == ("First retrieved chunk.\nSecond retrieved chunk.")


def test_map_omits_evidence_text_when_context_is_empty() -> None:
    mapper = AgentResponseMapper(agent_name="legal")
    response = mapper.map(
        state=_state(),
        execution_id="exec-1",
        context=(),
    )

    assert "evidence_text" not in response.metadata


def test_map_omits_evidence_text_when_context_items_have_no_content() -> None:
    context = (
        RetrievedContentDTO(
            source=RetrievalSourceEnum.DOCUMENT,
            source_name="empty-source",
            content="",
            score=None,
        ),
    )

    mapper = AgentResponseMapper(agent_name="legal")
    response = mapper.map(
        state=_state(),
        execution_id="exec-1",
        context=context,
    )

    assert "evidence_text" not in response.metadata


def test_map_marks_an_accepted_answer_as_verified() -> None:
    response = AgentResponseMapper(agent_name="legal").map(
        state=_state(),
        execution_id="exec-1",
        evaluation_summary=AnswerEvaluationSummary(groundedness=0.8, relevance=0.7),
    )

    assert response.metadata["answer_verified"] is True
    assert response.metadata["groundedness"] == 0.8
    assert response.metadata["relevance"] == 0.7


def test_map_marks_a_rejected_answer_as_unverified_with_its_scores() -> None:
    response = AgentResponseMapper(agent_name="legal").map(
        state=_state(),
        execution_id="exec-1",
        evaluation_summary=AnswerEvaluationSummary(
            groundedness=0.2,
            relevance=0.3,
            verified=False,
        ),
    )

    assert response.metadata["answer_verified"] is False
    assert response.metadata["groundedness"] == 0.2
    assert response.metadata["relevance"] == 0.3


def test_map_omits_answer_verified_when_no_evaluation_ran() -> None:
    response = AgentResponseMapper(agent_name="legal").map(
        state=_state(),
        execution_id="exec-1",
    )

    assert "answer_verified" not in response.metadata


def test_map_never_cites_the_runtimes_or_the_gates_own_notes() -> None:
    """
    Notes the runtime adds for the model (a rejected tool call, a gate
    rejection) are not sources: they appear in no citation, source or
    evidence text. Before, the gate's notes were listed as citations.
    """

    from agentic.agents.runtime.feedback import (
        CORRECTIVE_RETRIEVAL_FEEDBACK,
        EVALUATION_FEEDBACK,
        runtime_feedback,
    )

    evidence = RetrievedContentDTO(
        source=RetrievalSourceEnum.DOCUMENT,
        source_name="statute",
        content="Section 43: penalty for damage.",
        score=0.9,
    )
    notes = (
        runtime_feedback("Your call to tool 'retriever' failed."),
        RetrievedContentDTO(
            source=RetrievalSourceEnum.MEMORY,
            source_name="answer_evaluator",
            content="Previous answer was insufficient.",
            metadata={"source_type": EVALUATION_FEEDBACK},
        ),
        RetrievedContentDTO(
            source=RetrievalSourceEnum.MEMORY,
            source_name="answer_evaluator",
            content="Previous answer failed quality checks.",
            metadata={"source_type": CORRECTIVE_RETRIEVAL_FEEDBACK},
        ),
    )

    response = AgentResponseMapper(agent_name="legal").map(
        state=_state(),
        execution_id="exec-1",
        context=(notes[0], evidence, *notes[1:]),
    )

    assert [citation.source for citation in response.citations] == ["statute"]
    assert [source.title for source in response.sources] == ["statute"]
    assert response.metadata["evidence_text"] == "Section 43: penalty for damage."
