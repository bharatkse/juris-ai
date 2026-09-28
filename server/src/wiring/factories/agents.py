"""
Runtime agent composition.

Creates and registers all AI agents.

Responsibilities:

* Create agent instances
* Choose the agents' LLM client (Groq, with optional local failover)
* Register agents

Agents' CollaborationBus handlers are DelegatedAgentRunners, registered by
the executor factory (a delegated turn runs on the execution runtime, not
on the agent). No business logic belongs in this module.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from adapters.clients.llm.base import LLMClient
from adapters.clients.llm.failover import FailoverLLMClient
from agentic.agents.contract import ContractAgent
from agentic.agents.legal import LegalAgent
from agentic.agents.prompts.token_budget import (
    DEFAULT_RESERVED_OUTPUT_TOKENS,
    FIXED_SAFETY_MARGIN_TOKENS,
    context_window_for,
    estimate_tokens,
)
from core.dto.clients.llm import LLMRequestDTO
from core.dto.inference import InferencePolicy
from core.enums import LLMProviderEnum
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

    llm_client = build_agent_llm_client(
        settings=settings,
        clients=clients,
    )

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


def build_agent_llm_client(
    *,
    settings: Settings,
    clients: ClientContainer,
) -> LLMClient:
    """
    The LLM client every agent reasons with.

    Groq (the resolver's default provider). With LLM_LOCAL set to a local
    backend, Groq wrapped in a FailoverLLMClient that repeats a call on
    the local Ollama client when Groq is unavailable (review R2).

    A failed-over call reuses the prompt as built: the messages are plain
    role/content, which Ollama renders with the local model's own chat
    template, and the decision schema limits tool names in both
    providers. Agents never send tools= (review A19: on Ollama that
    output is unconstrained and out-of-list calls vanish). What differs is
    the context window, so a prompt budgeted for Groq that doesn't fit
    the local model's window is not failed over.
    """

    primary = clients.llm_resolver.get(LLMProviderEnum.GROQ)

    if not settings.llm.agent_local_failover:
        return primary

    fallback = clients.llm_resolver.get(LLMProviderEnum.LOCAL)
    fallback_window = context_window_for(fallback.model)

    def fits_fallback(request: LLMRequestDTO) -> bool:
        prompt_tokens = sum(estimate_tokens(message.content) for message in request.messages)
        output_tokens = request.inference.max_output_tokens or DEFAULT_RESERVED_OUTPUT_TOKENS

        return prompt_tokens + output_tokens + FIXED_SAFETY_MARGIN_TOKENS <= fallback_window

    return FailoverLLMClient(
        primary=primary,
        fallback=fallback,
        fits_fallback=fits_fallback,
    )
