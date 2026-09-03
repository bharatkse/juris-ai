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

from agentic.agents.contract import ContractAgent
from agentic.agents.legal import LegalAgent
from runtime.containers import ClientContainer, RegistryContainer


def register_agents(*, clients: ClientContainer, registries: RegistryContainer) -> None:
    retriever = registries.tool_registry.resolve(key="retriever")
    llm_client = clients.llm_resolver.get()  # default provider (Groq)

    legal_agent = LegalAgent(llm_client=llm_client, retriever=retriever)
    contract_agent = ContractAgent(llm_client=llm_client, retriever=retriever)

    registries.agent_registry.register(component=legal_agent)
    registries.agent_registry.register(component=contract_agent)
