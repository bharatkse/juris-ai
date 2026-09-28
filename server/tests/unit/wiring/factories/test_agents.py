"""
Unit tests for the agents' LLM client (wiring/factories/agents.py).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from adapters.clients.llm.failover import FailoverLLMClient
from adapters.clients.llm.groq import GroqClient
from adapters.clients.llm.local import LocalLLMClient
from config.llm import LLMSettings
from config.settings import get_settings
from core.dto.clients.llm import LLMMessageDTO, LLMRequestDTO
from core.enums import LLMProviderEnum, MessageRoleEnum
from wiring.factories.agents import build_agent_llm_client
from wiring.factories.llm_resolver import build_llm_resolver


def _build(*, failover: bool):
    settings = get_settings()
    resolver = build_llm_resolver(settings=settings)
    client = build_agent_llm_client(
        settings=SimpleNamespace(llm=SimpleNamespace(agent_local_failover=failover)),
        clients=SimpleNamespace(llm_resolver=resolver),
    )
    return client, resolver


def _request(words: int) -> LLMRequestDTO:
    return LLMRequestDTO(
        messages=(LLMMessageDTO(role=MessageRoleEnum.USER, content="word " * words),),
    )


def test_without_local_failover_agents_use_groq_only() -> None:
    client, resolver = _build(failover=False)

    assert isinstance(client, GroqClient)
    assert client is resolver.get(LLMProviderEnum.GROQ)


def test_with_local_failover_agents_use_groq_then_the_local_model() -> None:
    client, resolver = _build(failover=True)

    assert isinstance(client, FailoverLLMClient)
    assert client._primary is resolver.get(LLMProviderEnum.GROQ)
    assert isinstance(client._fallback, LocalLLMClient)
    # Prompts are still budgeted for Groq.
    assert client.model == resolver.get(LLMProviderEnum.GROQ).model


def test_only_prompts_that_fit_the_local_window_are_failed_over() -> None:
    client, _ = _build(failover=True)

    assert client._fits_fallback(_request(1_000))
    # qwen3's window is 32,768 tokens; ~40k words can't fit.
    assert not client._fits_fallback(_request(40_000))


@pytest.mark.parametrize(
    ("value", "enabled"),
    [("ollama", True), ("local", True), ("none", False)],
)
def test_llm_local_decides_agent_failover(value: str, enabled: bool) -> None:
    llm = get_settings().llm.model_copy(update={"LLM_LOCAL": value})

    assert llm.agent_local_failover is enabled


def test_llm_local_defaults_to_no_failover_and_rejects_unknown_values() -> None:
    assert LLMSettings.model_fields["LLM_LOCAL"].default == "none"

    with pytest.raises(ValidationError):
        LLMSettings(LLM_LOCAL="groq", SEARXNG_BASE_URL="http://searxng:8080")
