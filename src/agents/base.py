"""
Base AI agent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.agents.models import AgentRequest, AgentResponse
from src.agents.stream import AgentStream


class BaseAgent(ABC):
    """
    Base class for all AI agents.
    """

    @abstractmethod
    async def answer(
        self,
        *,
        request: AgentRequest,
    ) -> AgentResponse:
        """
        Generate an answer.
        """
        raise NotImplementedError

    @abstractmethod
    def stream_answer(
        self,
        request: AgentRequest,
    ) -> AgentStream:
        """
        Create a streaming response.
        """
        raise NotImplementedError
