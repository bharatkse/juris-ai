"""
Agent policy guards.
"""

from __future__ import annotations

from agentic.policy.schemas import (
    AgentPolicy,
    PolicyCheckResult,
)
from agentic.policy.tool_permission import ToolPermissionGuard


class AgentPolicyGuard:
    """
    Stateless guard for agent-level policy constraints.

    The guard evaluates policy and returns an allow/deny result.

    It does not:
    - execute tools,
    - execute agents,
    - perform user/tenant authorization,
    - evaluate HITL approval,
    - mutate agent state.
    """

    def __init__(
        self,
        *,
        tool_permission_guard: ToolPermissionGuard,
    ) -> None:
        self._tool_permission_guard = tool_permission_guard

    def check_tool(
        self,
        *,
        policy: AgentPolicy,
        tool_name: str,
    ) -> PolicyCheckResult:
        """Check whether the agent can use a tool."""

        return self._tool_permission_guard.check(
            policy=policy,
            tool_name=tool_name,
        )

    def check_delegation(
        self,
        *,
        policy: AgentPolicy,
        target_agent_id: str,
    ) -> PolicyCheckResult:
        """Check whether the agent can delegate to another agent."""

        if not policy.allow_delegation:
            return PolicyCheckResult(
                allowed=False,
                reason=(f"Agent '{policy.agent_id}' is not permitted " "to delegate."),
            )

        if not target_agent_id:
            return PolicyCheckResult(
                allowed=False,
                reason="Target agent ID is required.",
            )

        if target_agent_id not in policy.allowed_agents:
            return PolicyCheckResult(
                allowed=False,
                reason=(
                    f"Delegation to agent '{target_agent_id}' "
                    f"is not permitted for agent "
                    f"'{policy.agent_id}'."
                ),
            )

        return PolicyCheckResult(allowed=True)

    def check_citations(
        self,
        *,
        policy: AgentPolicy,
        has_citations: bool,
    ) -> PolicyCheckResult:
        """
        Check whether the citation requirement is satisfied.

        This only checks policy compliance. It does not validate
        whether citations actually support the response.
        """

        if policy.require_citations and not has_citations:
            return PolicyCheckResult(
                allowed=False,
                reason=(f"Agent '{policy.agent_id}' requires citations."),
            )

        return PolicyCheckResult(allowed=True)
