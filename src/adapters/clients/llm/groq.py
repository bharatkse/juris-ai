"""
Groq LLM client.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from groq import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncGroq,
    AuthenticationError,
    RateLimitError,
)

from adapters.clients.helper import map_exception
from adapters.clients.llm.base import LLMClient
from adapters.observability.logger import get_logger
from core.dto.clients.llm import (
    LLMMessageDTO,
    LLMRequestDTO,
    LLMResponseDTO,
    LLMStreamChunkDTO,
    LLMTokenUsageDTO,
)
from core.exceptions.client import (
    ClientAuthenticationError,
    ClientConnectionError,
    ClientProviderError,
    ClientRateLimitError,
    ClientTimeoutError,
)

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
        request: LLMRequestDTO,
    ) -> LLMResponseDTO:
        """
        Generate a completion.
        """

        log.info(
            "Generating completion using provider '%s', model '%s'.",
            self.provider,
            self.model,
        )

        request_kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": self._to_messages(
                request.messages,
            ),
            "temperature": request.temperature,
        }

        if request.max_tokens is not None:
            request_kwargs["max_tokens"] = request.max_tokens

        if request.response_format is not None:
            request_kwargs["response_format"] = request.response_format

            log.debug(
                "Using structured response format for provider '%s'.",
                self.provider,
            )

        log.info(
            "LLM request details.",
            extra={
                "response_format": request.response_format,
                "message_count": len(request.messages),
            },
        )

        try:
            response = await self._client.chat.completions.create(
                **request_kwargs,
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

        content = choice.message.content

        if not content or not content.strip():
            log.error(
                "Provider '%s' returned an empty completion.",
                self.provider,
                extra={
                    "model": self.model,
                    "finish_reason": choice.finish_reason,
                    "response_id": response.id,
                },
            )

            raise ClientProviderError(
                message=(f"Provider '{self.provider}' returned an empty completion."),
            )

        log.info(
            "Generated completion using provider '%s'. Finish reason: %s.",
            self.provider,
            choice.finish_reason,
        )

        return LLMResponseDTO(
            content=content,
            provider=self.provider,
            model=self.model,
            finish_reason=choice.finish_reason,
            usage=(
                LLMTokenUsageDTO(
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
        request: LLMRequestDTO,
    ) -> AsyncIterator[LLMStreamChunkDTO]:
        """
        Stream a completion.
        """

        log.info(
            "Starting streamed completion using provider '%s', model '%s'.",
            self.provider,
            self.model,
        )

        request_kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": self._to_messages(
                request.messages,
            ),
            "temperature": request.temperature,
            "stream": True,
        }

        if request.max_tokens is not None:
            request_kwargs["max_tokens"] = request.max_tokens

        if request.response_format is not None:
            request_kwargs["response_format"] = request.response_format

        try:
            stream = await self._client.chat.completions.create(
                **request_kwargs,
            )

            async for chunk in stream:
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]

                if choice.delta is None:
                    continue

                if choice.finish_reason is not None:
                    log.info(
                        "Completed streamed response using provider '%s'. " "Finish reason: %s.",
                        self.provider,
                        choice.finish_reason,
                    )

                yield LLMStreamChunkDTO(
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
            LLMMessageDTO,
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
