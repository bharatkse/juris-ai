"""
Groq LLM client.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import NoReturn, TypedDict

from groq import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncGroq,
    AuthenticationError,
    RateLimitError,
)

from src.clients.base import BaseLLMClient
from src.clients.exceptions import (
    LLMAuthenticationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from src.clients.models import LLMChunk, LLMMessage, LLMResponse, LLMTokenUsage
from src.core.config import settings
from src.core.enums import LLMProvider


class GroqChatMessage(TypedDict):
    role: str
    content: str


class GroqClient(BaseLLMClient):
    """
    Groq LLM provider.
    """

    PROVIDER = LLMProvider.GROQ

    def __init__(self) -> None:
        self._client = AsyncGroq(
            api_key=settings.GROQ_API_KEY.get_secret_value(),
        )

        self._model = settings.GROQ_MODEL

    @property
    def provider(self) -> str:
        return self.PROVIDER.value

    @property
    def model(self) -> str:
        return self._model

    async def generate(
        self,
        *,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """
        Generate a completion using Groq.
        """

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=self._build_messages(messages),
                temperature=temperature,
                max_tokens=max_tokens,
            )

            choice = response.choices[0]

            usage = None

            if response.usage:
                usage = LLMTokenUsage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                )

            return LLMResponse(
                content=choice.message.content or "",
                provider=self.PROVIDER.value,
                model=response.model,
                finish_reason=choice.finish_reason,
                usage=usage,
            )

        except Exception as exc:
            self._raise_provider_exception(exc)

    async def stream(
        self,
        *,
        messages: list[LLMMessage],
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> AsyncIterator[LLMChunk]:
        """
        Stream a completion from Groq.

        Yields:
            Text chunks produced by the language model.
        """
        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=self._build_messages(messages),
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            async for chunk in stream:
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]

                delta = choice.delta

                if delta is None:
                    continue

                content = delta.content or ""

                if not content and choice.finish_reason is None:
                    continue

                yield LLMChunk(
                    content=content,
                    is_final=choice.finish_reason is not None,
                    finish_reason=choice.finish_reason,
                )

        except Exception as exc:
            self._raise_provider_exception(exc)

    def _build_messages(
        self,
        messages: list[LLMMessage],
    ) -> list[GroqChatMessage]:
        """
        Convert domain messages into Groq request messages.
        """

        return [
            {
                "role": message.role.value,
                "content": message.content,
            }
            for message in messages
        ]

    @staticmethod
    def _raise_provider_exception(exc: Exception) -> NoReturn:
        """
        Translate Groq SDK exceptions into application exceptions.
        """

        if isinstance(exc, AuthenticationError):
            raise LLMAuthenticationError("Failed to authenticate with Groq.") from exc

        if isinstance(exc, RateLimitError):
            raise LLMRateLimitError("Groq rate limit exceeded.") from exc

        if isinstance(exc, APITimeoutError):
            raise LLMTimeoutError("Groq request timed out.") from exc

        if isinstance(exc, (APIConnectionError | APIStatusError)):
            raise LLMProviderError("Groq request failed.") from exc

        raise LLMProviderError("Unexpected error while communicating with Groq.") from exc
