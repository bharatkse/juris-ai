"""
Fixtures for Groq client tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.clients.llm.groq import GroqClient
from src.core.config import settings


@pytest.fixture
def mock_groq_client() -> MagicMock:
    """
    Return a mocked AsyncGroq client.
    """

    client = MagicMock()

    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock()

    return client


@pytest.fixture
def groq_client(
    mock_groq_client: MagicMock,
) -> GroqClient:
    """
    Return a GroqClient with a mocked SDK client.
    """

    client = GroqClient(
        api_key="test-api-key",
        model=settings.GROQ_MODEL,
    )

    client._client = mock_groq_client

    return client


@pytest.fixture
def mock_chat_completion(
    mock_groq_client: MagicMock,
) -> AsyncMock:
    """
    Return the mocked Groq completion method.
    """

    return mock_groq_client.chat.completions.create
