"""
Agent runtime context.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentic.execution.bus import CollaborationBus


@dataclass(slots=True)
class AgentRuntimeContext:
    """
    Request-scoped runtime services available to an agent.
    """

    collaboration_bus: CollaborationBus
