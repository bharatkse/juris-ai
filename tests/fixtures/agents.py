"""
Fixtures for AI agent tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.legal import LegalAgent
from src.clients.llm.base import LLMClient
from src.core.config import settings
from src.core.enums import LLMProvider
from src.tools.retrieval import RetrieverTool


@pytest.fixture
def mock_llm_client() -> LLMClient:
    """
    Return a mocked LLM client for agent tests.
    """

    client = MagicMock(
        spec=LLMClient,
    )

    client.provider = LLMProvider.GROQ.value
    client.model = settings.GROQ_MODEL

    client.generate = AsyncMock()
    client.stream = MagicMock()

    return client


@pytest.fixture
def mock_retriever() -> RetrieverTool:
    """
    Return a mocked retriever tool for agent tests.
    """

    return MagicMock(
        spec=RetrieverTool,
    )


@pytest.fixture
def legal_agent(
    mock_llm_client: LLMClient,
    mock_retriever: RetrieverTool,
) -> LegalAgent:
    """
    Return a LegalAgent with mocked dependencies.
    """

    return LegalAgent(
        llm_client=mock_llm_client,
        retriever=mock_retriever,
    )
