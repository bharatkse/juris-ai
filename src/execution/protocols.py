"""
Execution runtime protocols.
"""

from __future__ import annotations

from typing import Any, Protocol

from src.core.dto.planning import ExecutionStepDTO
from src.core.schemas.message import AgentMessageSchema
from src.execution.graph.state import ExecutionGraphState


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
