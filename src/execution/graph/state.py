"""
LangGraph execution state.
"""

from __future__ import annotations

from datetime import datetime
from operator import add
from typing import Annotated, Any, TypedDict
from uuid import UUID

from src.core.dto.action import ActionRequestDTO
from src.core.dto.agent import AgentContextDTO
from src.core.dto.conversation import ConversationDTO
from src.core.dto.planning import ExecutionPlanDTO
from src.core.enums import ExecutionStatusEnum


class ExecutionStepUpdate(TypedDict):
    """
    Immutable execution-state update produced by a graph node.
    """

    step_id: str

    status: ExecutionStatusEnum

    retry_count: int

    started_at: datetime | None

    completed_at: datetime | None

    error: str | None


class ExecutionArtifactUpdate(TypedDict):
    """
    Immutable execution-memory update produced by a graph node.
    """

    key: str

    value: Any


class ExecutionGraphState(TypedDict):
    """
    LangGraph runtime state.

    Graph state contains immutable/update-oriented values rather than
    mutable ExecutionStateSchema or ExecutionMemorySchema instances.

    This allows multiple parallel nodes to safely emit updates to the
    same channels.
    """

    request_id: UUID

    conversation: ConversationDTO
    context: AgentContextDTO

    plan: ExecutionPlanDTO

    execution_state_updates: Annotated[
        list[ExecutionStepUpdate],
        add,
    ]

    memory_updates: Annotated[
        list[ExecutionArtifactUpdate],
        add,
    ]

    action: ActionRequestDTO | None
