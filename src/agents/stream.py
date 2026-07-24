"""
Streaming support for AI agents.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from src.agents.models import AgentChunk, AgentResponse


class AgentStream(ABC):
    """
    Represents a streaming response from an AI agent.
    """

    @abstractmethod
    def __aiter__(self) -> AsyncIterator[AgentChunk]:
        """
        Iterate over streamed chunks.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def response(self) -> AgentResponse:
        """
        Final response available after the stream completes.
        """
        raise NotImplementedError
