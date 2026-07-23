"""
Base AI agent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.agents.models import AgentResponse


class BaseAgent(ABC):
    """
    Base class for all AI agents.
    """

    @abstractmethod
    async def answer(
        self,
        *,
        question: str,
    ) -> AgentResponse:
        """
        Generate an answer.
        """
        raise NotImplementedError
