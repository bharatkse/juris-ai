"""
Agent policy schemas.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PolicyCheckResult:
    """
    Result of an agent policy check.

    Policy denial is an expected result and is represented by
    allowed=False rather than an exception.
    """

    allowed: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ToolPermission:
    """Permission for an agent to use a specific tool."""

    tool_name: str
    allowed: bool = True


@dataclass(frozen=True, slots=True)
class AgentPermission:
    """Permission for an agent to delegate to another agent."""

    agent_id: str
    allowed: bool = True


@dataclass(frozen=True, slots=True)
class AgentPolicy:
    """
    Policy governing an agent's capabilities and behavior.

    Execution budgets are intentionally not part of this policy.
    """

    agent_id: str

    allowed_tools: frozenset[str] = frozenset()
    allowed_agents: frozenset[str] = frozenset()

    allow_delegation: bool = False
    require_citations: bool = False
