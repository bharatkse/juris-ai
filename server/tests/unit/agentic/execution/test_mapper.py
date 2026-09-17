"""
Unit tests for AgentResponseMapper.
"""

from __future__ import annotations

from datetime import UTC, datetime

from agentic.agents.runtime.lifecycle.budget import AgentExecutionBudget
from agentic.agents.runtime.lifecycle.state import AgentState
from agentic.agents.runtime.lifecycle.termination import AgentExecutionStatus
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
