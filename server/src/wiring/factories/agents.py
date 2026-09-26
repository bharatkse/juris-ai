"""
Runtime agent composition.

Creates and registers all AI agents.

Responsibilities:

* Create agent instances
* Register agents

Agents' CollaborationBus handlers are DelegatedAgentRunners, registered by
the executor factory (a delegated turn runs on the execution runtime, not
on the agent). No business logic belongs in this module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentic.agents.contract import ContractAgent
from agentic.agents.legal import LegalAgent
from core.dto.inference import InferencePolicy
from wiring.containers import ClientContainer, RegistryContainer

if TYPE_CHECKING:
    from config.settings import Settings


def register_agents(
    *,
    settings: Settings,
    clients: ClientContainer,
    registries: RegistryContainer,
) -> None:
    """
    Create and register all runtime agents in the AgentRegistry.

    Agent instances themselves remain stateless.
    """
    inference_policy = InferencePolicy(
        default_temperature=settings.llm.LLM_TEMPERATURE,
        default_top_p=settings.llm.LLM_TOP_P,
        default_max_output_tokens=settings.llm.LLM_MAX_OUTPUT_TOKENS,
    )

    llm_client = clients.llm_resolver.get()

    legal_agent = LegalAgent(
        llm_client=llm_client,
        inference_policy=inference_policy,
    )

    contract_agent = ContractAgent(
        llm_client=llm_client,
        inference_policy=inference_policy,
    )

    registries.agent_registry.register(
        component=legal_agent,
    )

    registries.agent_registry.register(
        component=contract_agent,
    )
