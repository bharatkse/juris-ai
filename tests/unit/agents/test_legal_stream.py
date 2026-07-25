"""
Unit tests for LegalAgentStream.
"""

from __future__ import annotations

import pytest

from src.agents.legal_stream import LegalAgentStream
from src.agents.models import AgentChunk
from tests.builders.groq import build_groq_stream
from tests.builders.llm import build_llm_chunk


def test_response_before_stream_raises(
    legal_agent_stream: LegalAgentStream,
) -> None:
    """
    It should raise when the response is accessed before streaming completes.
    """

    with pytest.raises(
        RuntimeError,
        match="Streaming has not completed.",
    ):
        _ = legal_agent_stream.response


@pytest.mark.asyncio
async def test_stream_yields_single_chunk(
    legal_agent_stream: LegalAgentStream,
    mock_llm_client,
) -> None:
    """
    It should yield a single streamed chunk.
    """

    mock_llm_client.stream.return_value = build_groq_stream(
        build_llm_chunk(
            content="Hello",
        ),
    )

    chunks = [chunk async for chunk in legal_agent_stream]

    assert chunks == [
        AgentChunk(
            content="Hello",
            is_final=False,
            finish_reason=None,
            metadata={},
        ),
    ]


@pytest.mark.asyncio
async def test_stream_yields_multiple_chunks(
    legal_agent_stream: LegalAgentStream,
    mock_llm_client,
) -> None:
    """
    It should preserve the order of streamed chunks.
    """

    mock_llm_client.stream.return_value = build_groq_stream(
        build_llm_chunk(
            content="Hello",
        ),
        build_llm_chunk(
            content=" ",
        ),
        build_llm_chunk(
            content="World",
        ),
        build_llm_chunk(
            content="",
            is_final=True,
            finish_reason="stop",
        ),
    )

    chunks = [chunk async for chunk in legal_agent_stream]

    assert chunks == [
        AgentChunk(
            content="Hello",
        ),
        AgentChunk(
            content=" ",
        ),
        AgentChunk(
            content="World",
        ),
        AgentChunk(
            content="",
            is_final=True,
            finish_reason="stop",
        ),
    ]


@pytest.mark.asyncio
async def test_stream_accumulates_content(
    legal_agent_stream: LegalAgentStream,
    mock_llm_client,
) -> None:
    """
    It should accumulate streamed content into the final response.
    """

    mock_llm_client.stream.return_value = build_groq_stream(
        build_llm_chunk(
            content="Hello",
        ),
        build_llm_chunk(
            content=" ",
        ),
        build_llm_chunk(
            content="World",
        ),
        build_llm_chunk(
            content="",
            is_final=True,
            finish_reason="stop",
        ),
    )

    async for _ in legal_agent_stream:
        pass

    response = legal_agent_stream.response

    assert response.content == "Hello World"
    assert response.finish_reason == "stop"


@pytest.mark.asyncio
async def test_stream_ignores_empty_content(
    legal_agent_stream: LegalAgentStream,
    mock_llm_client,
) -> None:
    """
    It should ignore empty content while building the final response.
    """

    mock_llm_client.stream.return_value = build_groq_stream(
        build_llm_chunk(
            content="Hello",
        ),
        build_llm_chunk(
            content="",
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

    async for _ in legal_agent_stream:
        pass

    response = legal_agent_stream.response

    assert response.content == "Hello World"


@pytest.mark.asyncio
async def test_stream_propagates_finish_reason(
    legal_agent_stream: LegalAgentStream,
    mock_llm_client,
) -> None:
    """
    It should preserve the provider finish reason.
    """

    mock_llm_client.stream.return_value = build_groq_stream(
        build_llm_chunk(
            content="Hello",
        ),
        build_llm_chunk(
            content="",
            is_final=True,
            finish_reason="stop",
        ),
    )

    async for _ in legal_agent_stream:
        pass

    assert legal_agent_stream.response.finish_reason == "stop"


@pytest.mark.asyncio
async def test_stream_merges_metadata(
    legal_agent_stream: LegalAgentStream,
    mock_llm_client,
) -> None:
    """
    It should merge metadata from streamed chunks.
    """

    mock_llm_client.stream.return_value = build_groq_stream(
        build_llm_chunk(
            content="Hello",
            metadata={
                "citation": 1,
            },
        ),
        build_llm_chunk(
            content=" World",
            metadata={
                "source": "law",
            },
        ),
        build_llm_chunk(
            content="",
            is_final=True,
            finish_reason="stop",
        ),
    )

    async for _ in legal_agent_stream:
        pass

    assert legal_agent_stream.response.metadata == {
        "citation": 1,
        "source": "law",
    }


@pytest.mark.asyncio
async def test_stream_handles_missing_metadata(
    legal_agent_stream: LegalAgentStream,
    mock_llm_client,
) -> None:
    """
    It should handle chunks without metadata.
    """

    mock_llm_client.stream.return_value = build_groq_stream(
        build_llm_chunk(
            content="Hello",
            metadata=None,
        ),
        build_llm_chunk(
            content=" World",
            metadata={
                "source": "law",
            },
        ),
        build_llm_chunk(
            content="",
            is_final=True,
            finish_reason="stop",
        ),
    )

    async for _ in legal_agent_stream:
        pass

    assert legal_agent_stream.response.metadata == {
        "source": "law",
    }


@pytest.mark.asyncio
async def test_stream_sets_latency(
    legal_agent_stream: LegalAgentStream,
    mock_llm_client,
) -> None:
    """
    It should record response latency.
    """

    mock_llm_client.stream.return_value = build_groq_stream(
        build_llm_chunk(
            content="Hello",
        ),
        build_llm_chunk(
            content="",
            is_final=True,
            finish_reason="stop",
        ),
    )

    async for _ in legal_agent_stream:
        pass

    assert legal_agent_stream.response.latency_ms is not None
    assert legal_agent_stream.response.latency_ms >= 0


@pytest.mark.asyncio
async def test_response_after_stream_returns_agent_response(
    legal_agent_stream: LegalAgentStream,
    mock_llm_client,
) -> None:
    """
    It should build the final agent response after streaming completes.
    """

    mock_llm_client.stream.return_value = build_groq_stream(
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
            metadata={
                "source": "law",
            },
        ),
    )

    async for _ in legal_agent_stream:
        pass

    response = legal_agent_stream.response

    assert response.content == "Hello World"
    assert response.provider == mock_llm_client.provider
    assert response.model == mock_llm_client.model
    assert response.finish_reason == "stop"
    assert response.metadata == {
        "source": "law",
    }

    assert response.usage is None

    assert response.latency_ms is not None
    assert response.latency_ms >= 0
