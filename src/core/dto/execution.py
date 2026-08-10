"""
Execution runtime models.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.dto.conversation import ConversationDTO
from src.core.dto.planning import ExecutionPlanDTO
from src.execution.bus import CollaborationBus
from src.execution.schemas.memory import ExecutionMemorySchema
from src.execution.schemas.state import ExecutionStateSchema


@dataclass(slots=True, frozen=True)
class ExecutionRequestDTO:
    """
    Immutable execution request.
    """

    conversation: ConversationDTO

    plan: ExecutionPlanDTO


@dataclass(slots=True)
class ExecutionContextDTO:
    """
    Mutable runtime execution context.

    Shared by every execution step belonging to the same request.
    """

    state: ExecutionStateSchema

    memory: ExecutionMemorySchema

    bus: CollaborationBus
