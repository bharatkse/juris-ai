"""
Execution runtime protocols.
"""

from __future__ import annotations

from typing import Any, Protocol

from agentic.execution.graph.state import ExecutionGraphState
from core.dto.planning import ExecutionStepDTO
from core.models.message import AgentMessageSchema


class AgentMessageHandler(Protocol):
    """
    Handles inter-agent collaboration requests.
    """

    async def handle_message(
        self,
        *,
        message: AgentMessageSchema,
    ) -> object: ...


class StepNode(Protocol):
    """
    Runtime callback used by a LangGraph execution-step node.
    """

    async def __call__(
        self,
        state: ExecutionGraphState,
        *,
        step: ExecutionStepDTO,
    ) -> dict[str, Any]: ...
