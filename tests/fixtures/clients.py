"""
LLM client fixtures.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.clients.base import BaseLLMClient
from src.clients.models import LLMChunk, LLMResponse, LLMTokenUsage


@pytest.fixture
def llm_client() -> BaseLLMClient:
    """
    Return a mocked LLM client.
    """

    client = AsyncMock(spec=BaseLLMClient)

    client.provider = "groq"
    client.model = "llama-3.3-70b-versatile"

    client.generate.return_value = LLMResponse(
        content="This is a mocked response.",
        provider=client.provider,
        model=client.model,
        finish_reason="stop",
        usage=LLMTokenUsage(
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        ),
    )

    async def stream():
        yield LLMChunk(
            content="This ",
            is_final=False,
        )

        yield LLMChunk(
            content="is ",
            is_final=False,
        )

        yield LLMChunk(
            content="mocked.",
            is_final=True,
            finish_reason="stop",
        )

    client.stream.side_effect = stream

    return client
