from __future__ import annotations

from typing import Any

from agentic.agents.runtime.lifecycle.state import AgentState
from core.dto.agent import AgentResponseDTO


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
    ) -> AgentResponseDTO:
        metadata: dict[str, Any] = {
            "execution_id": state.execution_id,
            "status": state.status.value,
        }

        if state.termination_reason is not None:
            metadata["termination_reason"] = state.termination_reason.value

        return AgentResponseDTO(
            content=state.partial_response or "",
            agent_name=self._agent_name,
            metadata=metadata,
        )
