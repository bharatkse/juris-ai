"""
Runtime agent composition.

Creates and registers all AI agents.

Responsibilities:

* Create agent instances
* Resolve required tools
* Register agents
* Register agent collaboration handlers

No business logic belongs in this module.
"""

from __future__ import annotations

from agentic.agents.contract import ContractAgent
from agentic.agents.legal import LegalAgent
from agentic.collaboration.bus import CollaborationBus
from runtime.containers import ClientContainer, RegistryContainer


def register_agents(
    *,
    clients: ClientContainer,
    registries: RegistryContainer,
    collaboration_bus: CollaborationBus,
) -> None:
    """
    Create and register all runtime agents.

    ```
    Agent instances are registered in the AgentRegistry for normal
    execution and their collaboration handlers are registered in the
    shared CollaborationBus for agent-to-agent delegation.

    The bus is process-scoped and shared by the runtime composition
    root. Agent instances themselves remain stateless.
    """

    retriever = registries.tool_registry.resolve(
        key="retriever",
    )

    llm_client = clients.llm_resolver.get()

    legal_agent = LegalAgent(
        llm_client=llm_client,
        retriever=retriever,
    )

    contract_agent = ContractAgent(
        llm_client=llm_client,
        retriever=retriever,
    )

    registries.agent_registry.register(
        component=legal_agent,
    )

    registries.agent_registry.register(
        component=contract_agent,
    )

    collaboration_bus.register(
        agent=legal_agent.metadata.name,
        handler=legal_agent,
    )

    collaboration_bus.register(
        agent=contract_agent.metadata.name,
        handler=contract_agent,
    )
