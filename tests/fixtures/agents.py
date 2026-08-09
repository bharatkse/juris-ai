"""
Fixtures for AI agent tests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.legal import LegalAgent
from src.agents.legal_stream import LegalAgentStream
from src.clients.llm.base import LLMClient
from src.clients.models import LLMMessage, LLMStreamChunk
from src.core.config import settings
from src.core.enums import LLMProvider
from src.prompts.legal import LEGAL_SYSTEM_PROMPT
from tests.builders.groq import build_groq_stream
from tests.builders.llm import build_llm_chunk, build_llm_messages


@pytest.fixture
def mock_llm_client() -> LLMClient:
    """
    Mock LLM client.
    """

    client = MagicMock(spec=LLMClient)

    client.provider = LLMProvider.GROQ.value
    client.model = settings.GROQ_MODEL

    client.generate = AsyncMock()

    #
    # stream() returns an async iterator, not a coroutine.
    #
    client.stream = MagicMock()

    return client


@pytest.fixture
def llm_messages() -> list[LLMMessage]:
    """
    Build default LLM messages.
    """

    return build_llm_messages()


@pytest.fixture
def llm_stream() -> AsyncIterator[LLMStreamChunk]:
    """
    Build a default streamed LLM response.
    """

    return build_groq_stream(
        build_llm_chunk(
            content="Hello",
        ),
        build_llm_chunk(
            content=" World",
        ),
        build_llm_chunk(
            content="",
            is_final=True,
            finish_reason="stop",
        ),
    )


@pytest.fixture
def empty_llm_stream() -> AsyncIterator[LLMStreamChunk]:
    """
    Return an empty LLM stream.
    """

    return build_groq_stream()


@pytest.fixture
def legal_agent(
    mock_llm_client: LLMClient,
) -> LegalAgent:
    """
    Return a legal AI agent.
    """

    return LegalAgent(
        client=mock_llm_client,
        system_prompt=LEGAL_SYSTEM_PROMPT,
    )


@pytest.fixture
def legal_agent_stream(
    mock_llm_client: LLMClient,
    llm_messages: list[LLMMessage],
) -> LegalAgentStream:
    """
    Create a LegalAgentStream.
    """

    return LegalAgentStream(
        client=mock_llm_client,
        messages=llm_messages,
    )


@pytest.fixture
def mock_agent() -> MagicMock:
    """
    Return a mocked conversation repository.
    """

    return MagicMock(
        spec=LegalAgent,
    )
