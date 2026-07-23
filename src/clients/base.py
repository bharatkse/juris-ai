"""
Base LLM client.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.clients.models import LLMMessage, LLMResponse


class BaseLLMClient(ABC):
    """
    Base class for all LLM providers.
    """

    @abstractmethod
    async def generate(
        self,
        *,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        Generate a completion.
        """
        raise NotImplementedError
