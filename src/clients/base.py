"""
Base LLM client.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from src.clients.models import LLMChunk, LLMMessage, LLMResponse


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

    @abstractmethod
    async def stream(
        self,
        *,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """
        Stream a response token-by-token.

        Yields:
            Individual text chunks from the language model.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def provider(self) -> str:
        """
        Provider name.
        """

    @property
    @abstractmethod
    def model(self) -> str:
        """
        Default model name.
        """
