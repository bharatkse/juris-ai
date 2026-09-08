"""
Agent tool-permission checks.
"""

from __future__ import annotations

from agentic.policy.schemas import (
    AgentPolicy,
    PolicyCheckResult,
)


class ToolPermissionGuard:
    """
    Stateless guard for agent-to-tool permissions.

    This checks agent capability policy only.

    It does not:
    - execute tools,
    - perform user/tenant authorization,
    - evaluate HITL approval,
    - modify agent state.
    """

    def check(
        self,
        *,
        policy: AgentPolicy,
        tool_name: str,
    ) -> PolicyCheckResult:
        """Return whether the agent is permitted to use the tool."""

        if not tool_name:
            return PolicyCheckResult(
                allowed=False,
                reason="Tool name is required.",
            )

        if tool_name not in policy.allowed_tools:
            return PolicyCheckResult(
                allowed=False,
                reason=(f"Tool '{tool_name}' is not permitted " f"for agent '{policy.agent_id}'."),
            )

        return PolicyCheckResult(allowed=True)
