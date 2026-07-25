"""
Unit tests for AgentStream.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from src.agents.models import AgentChunk, AgentResponse
from src.agents.stream import AgentStream
from tests.builders.agent import build_agent_chunk, build_agent_response


class DummyAgentStream(AgentStream):
    """
    Concrete AgentStream implementation used for testing.
    """

    def __init__(self) -> None:
        self._response = build_agent_response()

    async def __aiter__(self) -> AsyncIterator[AgentChunk]:
        """
        Yield a single agent chunk.
        """

        yield build_agent_chunk()

    @property
    def response(self) -> AgentResponse:
        """
        Return the final agent response.
        """

        return self._response


def test_agent_stream_is_abstract() -> None:
    """
    It should not allow direct instantiation.
    """

    with pytest.raises(TypeError):
        AgentStream()


@pytest.mark.asyncio
async def test_aiter_returns_agent_chunks() -> None:
    """
    It should iterate over streamed agent chunks.
    """

    stream = DummyAgentStream()

    chunks = [chunk async for chunk in stream]

    assert chunks == [
        build_agent_chunk(),
    ]


def test_response_returns_agent_response() -> None:
    """
    It should expose the final agent response.
    """

    stream = DummyAgentStream()

    assert stream.response == build_agent_response()
