"""
Groq LLM client.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from groq import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncGroq,
    AuthenticationError,
    RateLimitError,
)

from src.clients.helper import map_exception
from src.clients.llm.base import LLMClient
from src.clients.models import (
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMStreamChunk,
    LLMTokenUsage,
)
from src.core.custom_exceptions.client import (
    ClientAuthenticationError,
    ClientConnectionError,
    ClientProviderError,
    ClientRateLimitError,
    ClientTimeoutError,
)
from src.core.logger import get_logger

log = get_logger(__name__)


class GroqClient(LLMClient):
    """
    Groq implementation of the LLM client.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
    ) -> None:
        self._client = AsyncGroq(
            api_key=api_key,
        )
        self._model = model

    @property
    def provider(
        self,
    ) -> str:
        return "groq"

    @property
    def model(
        self,
    ) -> str:
        return self._model

    async def generate(
        self,
        *,
        request: LLMRequest,
    ) -> LLMResponse:
        """
        Generate a completion.
        """

        log.info(
            "Generating completion using provider '%s', model '%s'.",
            self.provider,
            self.model,
        )

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=self._to_messages(
                    request.messages,
                ),
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

        except Exception as exc:
            log.exception(
                "Failed to generate completion using provider '%s', model '%s'.",
                self.provider,
                self.model,
            )

            raise map_exception(
                exc=exc,
                mappings={
                    AuthenticationError: lambda _: ClientAuthenticationError(),
                    RateLimitError: lambda _: ClientRateLimitError(),
                    APITimeoutError: lambda _: ClientTimeoutError(),
                    APIConnectionError: lambda _: ClientConnectionError(),
                    APIStatusError: lambda e: ClientProviderError(
                        message=str(e),
                    ),
                },
                default=lambda e: ClientProviderError(
                    message=str(e),
                ),
            ) from exc

        if not response.choices:
            log.error(
                "Provider '%s' returned no completion choices.",
                self.provider,
            )

            raise ClientProviderError(
                message="Groq returned no completion choices.",
            )

        choice = response.choices[0]

        log.info(
            "Generated completion using provider '%s'. Finish reason: %s.",
            self.provider,
            choice.finish_reason,
        )

        return LLMResponse(
            content=choice.message.content or "",
            provider=self.provider,
            model=self.model,
            finish_reason=choice.finish_reason,
            usage=(
                LLMTokenUsage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
                )
                if response.usage
                else None
            ),
            metadata={
                "id": response.id,
            },
        )

    async def stream(
        self,
        *,
        request: LLMRequest,
    ) -> AsyncIterator[LLMStreamChunk]:
        """
        Stream a completion.
        """

        log.info(
            "Starting streamed completion using provider '%s', model '%s'.",
            self.provider,
            self.model,
        )

        try:
            stream = await self._client.chat.completions.create(
                model=self._model,
                messages=self._to_messages(
                    request.messages,
                ),
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=True,
            )

            async for chunk in stream:
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]

                if choice.delta is None:
                    continue

                if choice.finish_reason is not None:
                    log.info(
                        "Completed streamed response using provider '%s'. Finish reason: %s.",
                        self.provider,
                        choice.finish_reason,
                    )

                yield LLMStreamChunk(
                    content=choice.delta.content or "",
                    is_final=choice.finish_reason is not None,
                    finish_reason=choice.finish_reason,
                )

        except Exception as exc:
            log.exception(
                "Failed to stream completion using provider '%s', model '%s'.",
                self.provider,
                self.model,
            )

            raise map_exception(
                exc=exc,
                mappings={
                    AuthenticationError: lambda _: ClientAuthenticationError(),
                    RateLimitError: lambda _: ClientRateLimitError(),
                    APITimeoutError: lambda _: ClientTimeoutError(),
                    APIConnectionError: lambda _: ClientConnectionError(),
                    APIStatusError: lambda e: ClientProviderError(
                        message=str(e),
                    ),
                },
                default=lambda e: ClientProviderError(
                    message=str(e),
                ),
            ) from exc

    @staticmethod
    def _to_messages(
        messages: tuple[
            LLMMessage,
            ...,
        ],
    ) -> list[dict[str, str]]:
        """
        Convert provider-independent messages into
        the Groq SDK message format.
        """

        return [
            {
                "role": message.role.value,
                "content": message.content,
            }
            for message in messages
        ]
