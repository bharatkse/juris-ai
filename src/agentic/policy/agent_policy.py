"""
Agent policy resolution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from agentic.policy.schemas import AgentPolicy


class AgentPolicyProvider(ABC):
    """
    Resolves the policy for an agent.

    Implementations may load policies from configuration,
    a database, or another policy source.
    """

    @abstractmethod
    async def get_policy(
        self,
        *,
        agent_id: str,
    ) -> AgentPolicy:
        """Return the policy applicable to an agent."""
        raise NotImplementedError


class StaticAgentPolicyProvider(AgentPolicyProvider):
    """
    Policy provider backed by immutable configuration.

    The provider does not mutate policies during execution.
    """

    def __init__(
        self,
        *,
        policies: dict[str, AgentPolicy],
    ) -> None:
        self._policies = dict(policies)

    async def get_policy(
        self,
        *,
        agent_id: str,
    ) -> AgentPolicy:
        policy = self._policies.get(agent_id)

        if policy is None:
            raise AgentPolicyNotFoundError(agent_id)

        return policy


class AgentPolicyNotFoundError(LookupError):
    """Raised when an agent has no configured policy."""

    def __init__(self, agent_id: str) -> None:
        super().__init__(f"No agent policy configured for agent '{agent_id}'.")
