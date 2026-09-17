"""
Execution runtime models.
"""

from __future__ import annotations

from dataclasses import dataclass

from execution.bus import CollaborationBus
from execution.schemas.memory import ExecutionMemorySchema
from execution.schemas.state import ExecutionStateSchema

from core.dto.conversation import ConversationDTO
from core.dto.planning import ExecutionPlanDTO


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
