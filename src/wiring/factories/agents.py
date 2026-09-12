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

from typing import TYPE_CHECKING

from agentic.agents.contract import ContractAgent
from agentic.agents.legal import LegalAgent
from agentic.collaboration.bus import CollaborationBus
from core.dto.inference import InferencePolicy
from wiring.containers import ClientContainer, RegistryContainer

if TYPE_CHECKING:
    from config.settings import Settings


def register_agents(
    *,
    settings: Settings,
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
    inference_policy = InferencePolicy(
        default_temperature=settings.llm.LLM_TEMPERATURE,
        default_top_p=settings.llm.LLM_TOP_P,
        default_max_output_tokens=settings.llm.LLM_MAX_OUTPUT_TOKENS,
    )

    retriever = registries.tool_registry.resolve(
        key="retriever",
    )

    llm_client = clients.llm_resolver.get()

    legal_agent = LegalAgent(
        llm_client=llm_client,
        retriever=retriever,
        inference_policy=inference_policy,
    )

    contract_agent = ContractAgent(
        llm_client=llm_client,
        retriever=retriever,
        inference_policy=inference_policy,
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
