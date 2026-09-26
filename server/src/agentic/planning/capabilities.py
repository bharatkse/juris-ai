"""
Agent capabilities for the planner.

Tells the planner which agents it can assign steps to and exactly which
tools each one's policy allows. Built from the same sources as an agent's
own tool catalog (AgentExecution.start()): the agent registry, the agent
policy provider and ToolRegistry.describe(). So a policy change reaches
the planner's prompt and the agent's prompt alike, with no template edit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adapters.observability.logger import get_logger
from agentic.policy.agent_policy import AgentPolicyNotFoundError
from core.dto.planning import AgentCapabilityDTO
from core.enums import AgentTypeEnum

if TYPE_CHECKING:
    from agentic.policy.agent_policy import AgentPolicyProvider
    from agentic.registry.protocols import AgentRegistryProtocol, ToolRegistryProtocol

logger = get_logger(__name__)


class AgentCapabilityCatalog:
    """
    Describes every agent a plan may use, with the tools its policy allows.
    """

    def __init__(
        self,
        *,
        agent_registry: AgentRegistryProtocol,
        tool_registry: ToolRegistryProtocol,
        agent_policy_provider: AgentPolicyProvider,
    ) -> None:
        self._agent_registry = agent_registry
        self._tool_registry = tool_registry
        self._agent_policy_provider = agent_policy_provider

    async def describe(
        self,
    ) -> tuple[AgentCapabilityDTO, ...]:
        """
        Return the plannable agents, in AgentTypeEnum order.

        A plan step's agent must be an AgentTypeEnum member (the plan
        schema enforces it). An agent that isn't registered, or has no
        policy, is left out: a step assigned to it would fail when it
        runs, so the planner shouldn't be offered it.
        """

        capabilities: list[AgentCapabilityDTO] = []

        for agent_type in AgentTypeEnum:
            if not self._agent_registry.exists(key=agent_type.value):
                continue

            try:
                policy = await self._agent_policy_provider.get_policy(
                    agent_id=agent_type.value,
                )
            except AgentPolicyNotFoundError:
                logger.warning(
                    "Agent '%s' has no policy; it is left out of the planner's agents.",
                    agent_type.value,
                )
                continue

            agent = self._agent_registry.resolve(key=agent_type.value)

            capabilities.append(
                AgentCapabilityDTO(
                    agent=agent_type,
                    description=agent.metadata.description,
                    tools=self._tool_registry.describe(names=policy.allowed_tools),
                ),
            )

        return tuple(capabilities)
