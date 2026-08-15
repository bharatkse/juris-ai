"""
Builders for execution runtime test state.
"""

from __future__ import annotations

from uuid import UUID

from src.core.dto.agent import AgentContextDTO
from src.core.dto.planning import ExecutionPlanDTO
from src.execution.graph.state import (
    ExecutionArtifactUpdate,
    ExecutionGraphState,
    ExecutionStepUpdate,
)
from tests.builders.conversation import build_conversation
from tests.builders.planning import build_plan
from tests.helpers.identifiers import unknown_request_id


def build_graph_state(
    *,
    request_id: UUID | None = None,
    execution_state_updates: list[ExecutionStepUpdate] | None = None,
    memory_updates: list[ExecutionArtifactUpdate] | None = None,
    plan: ExecutionPlanDTO | None = None,
    context: AgentContextDTO | None = None,
) -> ExecutionGraphState:
    """
    Build a valid LangGraph execution state for tests.
    """

    return {
        "request_id": request_id or unknown_request_id(),
        "conversation": build_conversation(),
        "plan": plan or build_plan(),
        "execution_state_updates": execution_state_updates or [],
        "memory_updates": memory_updates or [],
        "context": context or AgentContextDTO(),
    }
