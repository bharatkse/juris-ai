"""
Runtime agent composition.

Creates and registers all AI agents.

Responsibilities:

- Create agent instances
- Resolve required tools
- Register agents

No business logic belongs in this module.
"""

from __future__ import annotations

from src.agents.contract import ContractAgent
from src.agents.legal import LegalAgent
from src.runtime.containers import ClientContainer, RegistryContainer


def register_agents(
    *,
    clients: ClientContainer,
    registries: RegistryContainer,
) -> None:
    """
    Create and register all runtime agents.
    """

    retriever = registries.tool_registry.resolve(
        key="retriever",
    )

    legal_agent = LegalAgent(
        llm_client=clients.llm_client,
        retriever=retriever,
    )

    contract_agent = ContractAgent(
        llm_client=clients.llm_client,
        retriever=retriever,
    )

    registries.agent_registry.register(
        component=legal_agent,
    )

    registries.agent_registry.register(
        component=contract_agent,
    )
