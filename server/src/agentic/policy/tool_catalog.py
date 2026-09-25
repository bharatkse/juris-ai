"""
An agent's tool catalog: the tools its policy allows, as its prompt
describes them.

Same source as the normal execution path (AgentExecution.start()): the
agent's policy from the AgentPolicyProvider, then
ToolRegistry.describe(names=policy.allowed_tools). Used where an agent
reasons outside AgentExecution, i.e. an agent-to-agent collaboration
message (BaseAgent.handle_message()), so it is told its own tools there
too.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentic.policy.agent_policy import AgentPolicyProvider
    from agentic.registry.protocols import ToolRegistryProtocol
    from core.dto.tool import ToolSpecDTO


class AgentToolCatalog:
    """
    Describes the tools an agent's policy allows.
    """

    def __init__(
        self,
        *,
        agent_policy_provider: AgentPolicyProvider,
        tool_registry: ToolRegistryProtocol,
    ) -> None:
        self._agent_policy_provider = agent_policy_provider
        self._tool_registry = tool_registry

    async def describe(
        self,
        *,
        agent_id: str,
    ) -> tuple[ToolSpecDTO, ...]:
        """
        Return the agent's tool catalog.

        Raises AgentPolicyNotFoundError when the agent has no policy,
        as AgentExecution.start() does: an agent with no policy doesn't
        run.
        """

        policy = await self._agent_policy_provider.get_policy(
            agent_id=agent_id,
        )

        return self._tool_registry.describe(
            names=policy.allowed_tools,
        )
