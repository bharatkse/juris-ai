"""
Agent policy repository.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.models.agent_policy import AgentPolicyModel


class AgentPolicyRepository:
    """
    Repository for agent policy persistence.

    Read-heavy: policy resolution happens on the agent execution hot
    path (AgentExecution.start(), once per agent execution), so
    get_by_agent_id is the primary operation this repository exists
    for.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def get_by_agent_id(
        self,
        *,
        agent_id: str,
    ) -> AgentPolicyModel | None:
        """
        Return the policy row for ``agent_id``, or None if unconfigured.
        """

        result = await self._session.execute(
            select(AgentPolicyModel).where(
                AgentPolicyModel.agent_id == agent_id,
            )
        )

        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        agent_id: str,
        allowed_tools: list[str],
        enabled: bool = True,
    ) -> AgentPolicyModel:
        """
        Create or update the policy row for ``agent_id``.

        Used by the seed step (wiring/factories/agents.py) -- not part
        of the hot read path.
        """

        existing = await self.get_by_agent_id(agent_id=agent_id)

        if existing is not None:
            existing.allowed_tools = allowed_tools
            existing.enabled = enabled
            await self._session.flush()
            return existing

        policy = AgentPolicyModel(
            agent_id=agent_id,
            allowed_tools=allowed_tools,
            enabled=enabled,
        )
        self._session.add(policy)
        await self._session.flush()
        return policy
