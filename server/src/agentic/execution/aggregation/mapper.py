from __future__ import annotations

from typing import Any

from agentic.agents.runtime.lifecycle.state import AgentState
from agentic.evaluation.answer import AnswerEvaluationSummary
from core.dto.agent import AgentResponseDTO
from core.dto.response import CitationDTO, SourceDTO
from core.dto.tool import RetrievedContentDTO


class AgentResponseMapper:
    """
    Converts execution state into the existing AgentResponseDTO.

    The mapper does not retain execution state.
    """

    def __init__(
        self,
        *,
        agent_name: str,
    ) -> None:
        self._agent_name = agent_name

    def map(
        self,
        *,
        state: AgentState,
        execution_id: str,
        context: tuple[RetrievedContentDTO, ...] = (),
        evaluation_summary: AnswerEvaluationSummary | None = None,
    ) -> AgentResponseDTO:
        """
        Args:
            state:
                Request-scoped agent lifecycle state.
            execution_id:
                Identifies the originating request. AgentState carries
                no request-identity fields by design (see its own
                docstring) -- this must come from the caller's
                AgentRequestDTO.context.execution_id, not from state.
            context:
                Retrieved evidence accumulated on the execution handle
                (AgentExecutionHandle.reasoning_context) -- the only
                source of RetrievedContentDTO in this execution path.
                _retrieve_context() (agents/base.py) is a separate,
                run()-only method and does not feed this path.
            evaluation_summary:
                Groundedness/relevance from AgentContinuationService.
                _gate_final's accepted evaluation, when one ran (see
                AnswerEvaluationSummary's docstring) -- surfaced here
                so the compliance log (AIOrchestrator's AGENT_DECISION
                write) can read real scores instead of always None.
        """
        metadata: dict[str, Any] = {
            "execution_id": execution_id,
            "status": state.status.value,
        }

        if state.termination_reason is not None:
            metadata["termination_reason"] = state.termination_reason.value

        if evaluation_summary is not None:
            metadata["groundedness"] = evaluation_summary.groundedness
            metadata["relevance"] = evaluation_summary.relevance

        # Full, untruncated retrieved-evidence text -- the same
        # evidence _gate_final actually evaluated the answer against
        # (AgentContinuationService._gate_final builds its own
        # `evidence` tuple from this identical handle.reasoning_context).
        # Citations below are independently built from the same
        # `context` but truncate to a 280-char snippet for display;
        # this field exists so a downstream consumer that needs the
        # real evidence text (AIOrchestrator's output-guardrail PII-
        # provenance check, see orchestrator.py's _evidence_text) isn't
        # stuck working from that truncated proxy.
        evidence_text = "\n".join(item.content for item in context if item.content)

        if evidence_text:
            metadata["evidence_text"] = evidence_text

        citations, sources = self._build_provenance(context)

        return AgentResponseDTO(
            content=state.partial_response or "",
            agent_name=self._agent_name,
            metadata=metadata,
            citations=citations,
            sources=sources,
        )

    @staticmethod
    def _build_provenance(
        context: tuple[RetrievedContentDTO, ...],
    ) -> tuple[tuple[CitationDTO, ...], tuple[SourceDTO, ...]]:
        citations = tuple(
            CitationDTO(
                title=item.metadata.get("title") or item.source_name,
                source=item.source_name,
                snippet=item.content[:280] if item.content else None,
            )
            for item in context
        )
        sources = tuple(
            SourceDTO(
                title=item.metadata.get("title") or item.source_name,
                uri=item.metadata.get("source_id"),
                type=item.source.value,
            )
            for item in context
        )
        return citations, sources
