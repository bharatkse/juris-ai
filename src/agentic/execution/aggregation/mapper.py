from __future__ import annotations

from typing import Any

from agentic.agents.runtime.lifecycle.state import AgentState
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
        """
        metadata: dict[str, Any] = {
            "execution_id": execution_id,
            "status": state.status.value,
        }

        if state.termination_reason is not None:
            metadata["termination_reason"] = state.termination_reason.value

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
