"""
Builders for execution runtime test state.
"""

from __future__ import annotations

from uuid import UUID

from agentic.execution.graph.state import (
    ExecutionArtifactUpdate,
    ExecutionGraphState,
    ExecutionStepUpdate,
)
from core.dto.agent import AgentContextDTO
from core.dto.planning import ExecutionPlanDTO
from tests.builders.agentic.agent import build_agent_context
from tests.builders.agentic.planning import build_plan
from tests.builders.application.conversation import build_conversation
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
        "context": context or build_agent_context(),
    }
