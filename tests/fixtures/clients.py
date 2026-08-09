"""
LLM client fixtures.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.clients.llm.base import LLMClient
from src.clients.models import LLMResponse, LLMStreamChunk, LLMTokenUsage
from src.clients.storage.base import StorageClient
from src.core.enums import StorageType


@pytest.fixture
def llm_client() -> LLMClient:
    """
    Return a mocked LLM client.
    """

    client = AsyncMock(spec=LLMClient)

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
        yield LLMStreamChunk(
            content="This ",
            is_final=False,
        )

        yield LLMStreamChunk(
            content="is ",
            is_final=False,
        )

        yield LLMStreamChunk(
            content="mocked.",
            is_final=True,
            finish_reason="stop",
        )

    client.stream.side_effect = stream

    return client


@pytest.fixture
def mock_storage_client() -> StorageClient:
    """
    Return a mocked storage client.
    """

    client = AsyncMock(
        spec=StorageClient,
    )

    client.storage_type = StorageType.LOCAL

    return client
