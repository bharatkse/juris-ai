"""
Agent policy resolution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING

from adapters.persistence.sqlalchemy.repositories.agent_policy import (
    AgentPolicyRepository,
)
from agentic.policy.schemas import AgentPolicy

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


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


class DatabaseAgentPolicyProvider(AgentPolicyProvider):
    """
    Policy provider backed by the agent_policies table.

    Replaces StaticAgentPolicyProvider(policies=AGENT_POLICIES) in
    production now that AGENT_POLICIES is no longer the source of
    truth -- see agentic/policy/config.py. A disabled row (enabled=
    False) is treated the same as no row at all: rejected, not
    silently given zero permissions, matching this module's existing
    reject-by-default philosophy.

    allowed_agents, allow_delegation, and require_citations are not
    yet database-backed (see AgentPolicyModel's docstring) -- every
    resolved policy defaults them to frozenset()/False/False, which is
    what every agent already got implicitly before this table existed.

    Takes a session FACTORY, not a bound session/repository: this
    provider is built once as part of the process-lifetime Executor
    (wiring/factories/executor.py) and reused across every concurrent
    request, so it cannot hold one AsyncSession for its whole lifetime
    (sessions aren't safe to share across concurrent requests) -- a
    fresh session is opened per get_policy() call, the same pattern
    agentic/tools/library/file_lookup.py already uses for the same
    reason.
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def get_policy(
        self,
        *,
        agent_id: str,
    ) -> AgentPolicy:
        async with self._session_factory() as session:
            repository = AgentPolicyRepository(session=session)

            row = await repository.get_by_agent_id(
                agent_id=agent_id,
            )

        if row is None or not row.enabled:
            raise AgentPolicyNotFoundError(agent_id)

        return AgentPolicy(
            agent_id=row.agent_id,
            allowed_tools=frozenset(row.allowed_tools),
        )


class AgentPolicyNotFoundError(LookupError):
    """Raised when an agent has no configured policy."""

    def __init__(self, agent_id: str) -> None:
        super().__init__(f"No agent policy configured for agent '{agent_id}'.")
