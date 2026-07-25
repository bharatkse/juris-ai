"""
Test helpers for AgentStream.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from src.agents.models import AgentChunk, AgentResponse
from src.agents.stream import AgentStream


class DummyAgentStream(AgentStream):
    """
    Concrete AgentStream implementation used for testing.
    """

    def __init__(
        self,
        *,
        response: AgentResponse,
        chunks: list[AgentChunk],
    ) -> None:
        self._response = response
        self._chunks = chunks

    async def __aiter__(
        self,
    ) -> AsyncIterator[AgentChunk]:
        for chunk in self._chunks:
            yield chunk

    @property
    def response(
        self,
    ) -> AgentResponse:
        return self._response
