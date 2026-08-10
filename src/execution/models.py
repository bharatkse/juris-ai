"""
Execution runtime models.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.models.conversation import Conversation
from src.core.models.planning import ExecutionPlan
from src.execution.bus import CollaborationBus
from src.execution.memory import ExecutionMemory
from src.execution.state import ExecutionState


@dataclass(slots=True, frozen=True)
class ExecutionRequest:
    """
    Immutable execution request.
    """

    conversation: Conversation

    plan: ExecutionPlan


@dataclass(slots=True)
class ExecutionContext:
    """
    Mutable runtime execution context.

    Shared by every execution step belonging to the same request.
    """

    state: ExecutionState

    memory: ExecutionMemory

    bus: CollaborationBus
