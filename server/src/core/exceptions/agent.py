"""
Agent exceptions.

Agent exceptions are raised during agent execution.

These exceptions inherit from ``AIError`` and indicate failures
that occur while an agent is reasoning, collaborating with other
agents, or executing its assigned capability.

Agent lifecycle:

Executor
    │
    ▼
Agent.run()
    │
    ├── Read ExecutionMemory
    ├── Call CollaborationBus
    ├── Invoke Tools
    └── Produce Result
"""

from __future__ import annotations

from core.constants import (
    ERROR_AGENT,
    ERROR_AGENT_CAPABILITY,
    ERROR_AGENT_COLLABORATION,
    ERROR_AGENT_EXECUTION,
)
from core.exceptions.base import AIError


class AgentError(AIError):
    """
    Base exception for agent failures.
    """

    error_code = ERROR_AGENT
    default_message = "Agent operation failed."


class AgentExecutionError(AgentError):
    """
    Raised when an agent fails during execution.

    Examples:
        - Prompt execution failed
        - Unexpected runtime exception
        - Agent returned an invalid result
    """

    error_code = ERROR_AGENT_EXECUTION
    default_message = "Agent execution failed."


class AgentCapabilityError(AgentError):
    """
    Raised when an agent cannot execute the requested capability.

    Examples:
        - Unsupported capability
        - Capability not implemented
        - Invalid capability configuration
    """

    error_code = ERROR_AGENT_CAPABILITY
    default_message = "Unsupported agent capability."


class AgentCommunicationError(AgentError):
    """
    Raised when communication between agents fails.

    Examples:
        - Collaboration request rejected
        - Collaboration timeout
        - Invalid collaboration response
    """

    error_code = ERROR_AGENT_COLLABORATION
    default_message = "Agent communication failed."
