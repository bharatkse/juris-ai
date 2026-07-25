"""
Streaming implementation for the Legal AI agent.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator

from src.agents.models import AgentChunk, AgentResponse
from src.agents.stream import AgentStream
from src.clients.base import BaseLLMClient
from src.clients.models import LLMMessage


class LegalAgentStream(AgentStream):
    """
    Streaming implementation for the Legal AI agent.
    """

    def __init__(
        self,
        *,
        client: BaseLLMClient,
        messages: list[LLMMessage],
    ) -> None:
        self._client = client
        self._messages = messages

        self._started_at = time.perf_counter()

        self._content: list[str] = []

        self._response: AgentResponse | None = None

    def __aiter__(self) -> AsyncIterator[AgentChunk]:
        """
        Return the async iterator.
        """

        return self._stream()

    async def _stream(self) -> AsyncIterator[AgentChunk]:
        """
        Stream the response from the LLM.
        """

        usage = None
        finish_reason = None
        metadata: dict[str, object] = {}

        async for chunk in self._client.stream(
            messages=self._messages,
            temperature=0.2,
        ):
            if chunk.content:
                self._content.append(chunk.content)

            if chunk.finish_reason:
                finish_reason = chunk.finish_reason

            metadata.update(chunk.metadata or {})

            yield AgentChunk(
                content=chunk.content,
                is_final=chunk.is_final,
                finish_reason=chunk.finish_reason,
                metadata=chunk.metadata or {},
            )

        latency_ms = int(
            (time.perf_counter() - self._started_at) * 1000,
        )

        self._response = AgentResponse(
            content="".join(self._content),
            provider=self._client.provider,
            model=self._client.model,
            finish_reason=finish_reason,
            latency_ms=latency_ms,
            usage=usage,
            metadata=metadata,
        )

    @property
    def response(self) -> AgentResponse:
        """
        Return the final response.

        Raises:
            RuntimeError: If accessed before streaming completes.
        """

        if self._response is None:
            raise RuntimeError(
                "Streaming has not completed.",
            )

        return self._response
