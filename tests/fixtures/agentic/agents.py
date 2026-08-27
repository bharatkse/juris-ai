"""
Fixtures for AI agent tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.clients.llm.base import LLMClient
from agentic.agents.legal import LegalAgent
from agentic.tools.retrieval import RetrieverTool
from config.settings import get_settings
from core.enums import LLMProviderEnum

settings = get_settings()


@pytest.fixture
def mock_llm_client() -> LLMClient:
    """
    Return a mocked LLM client for agent tests.
    """

    client = MagicMock(
        spec=LLMClient,
    )

    client.provider = LLMProviderEnum.GROQ.value
    client.model = settings.llm.GROQ_MODEL

    client.run = AsyncMock()
    client.generate = AsyncMock()
    client.stream = MagicMock()

    return client


@pytest.fixture
def mock_retriever() -> RetrieverTool:
    """
    Return a mocked retriever tool for agent tests.
    """

    retriever = MagicMock(
        spec=RetrieverTool,
    )

    retriever.run = AsyncMock(
        return_value=MagicMock(
            content=(),
        ),
    )

    return retriever


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
