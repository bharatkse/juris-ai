"""
E2E: the hermetic_llm fixture catches a streaming generation.

Proves the fixture's S2 guard: /chat/stream must never stream model output
directly, and hermetic_llm is what fails an e2e test if a streaming
generation comes back. The concrete clients override stream(), so this
calls each real override rather than the base class.
"""

from __future__ import annotations

import pytest

from adapters.clients.llm.groq import GroqClient
from adapters.clients.llm.local import LocalLLMClient
from core.dto.clients.llm import LLMMessageDTO, LLMRequestDTO
from core.enums import MessageRoleEnum


@pytest.mark.asyncio
@pytest.mark.parametrize("client_class", [GroqClient, LocalLLMClient])
async def test_a_streaming_generation_is_recorded_as_an_unmocked_llm_call(
    hermetic_llm,
    client_class,
) -> None:
    # No provider connection is needed: the patched stream() never uses one.
    client = client_class.__new__(client_class)
    request = LLMRequestDTO(
        messages=(LLMMessageDTO(role=MessageRoleEnum.USER, content="second generation"),),
    )

    chunks = [chunk async for chunk in client.stream(request=request)]

    assert chunks == []
    assert hermetic_llm.unexpected_calls == ["stream: second generation"]

    # Recorded as intended; clear it so this test's own teardown passes.
    hermetic_llm.unexpected_calls.clear()
