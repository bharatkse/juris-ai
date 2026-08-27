"""
Local LLM client.

Provides an LLMClient implementation for local LLM inference
through Ollama.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ollama import AsyncClient, ResponseError

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
    ClientConnectionError,
    ClientProviderError,
    ClientTimeoutError,
)

log = get_logger(__name__)


class LocalLLMClient(LLMClient):
    """
    Local LLM implementation using Ollama.
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
    ) -> None:
        self._client = AsyncClient(
            host=base_url,
        )
        self._model = model
        self._think = False

        log.info(
            "Initialized local LLM client with Ollama. " "Base URL: '%s', model: '%s'.",
            base_url,
            model,
        )

    @property
    def provider(
        self,
    ) -> str:
        return "local"

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
        Generate a completion using the local LLM.
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
            "think": self._think,
        }

        if request.temperature is not None:
            request_kwargs["options"] = {
                "temperature": request.temperature,
            }

        if request.max_tokens is not None:
            request_kwargs.setdefault(
                "options",
                {},
            )["num_predict"] = request.max_tokens

        if request.response_format is not None:
            request_kwargs["format"] = self._to_response_format(
                request.response_format,
            )

            log.debug(
                "Using structured response format for provider '%s'.",
                self.provider,
            )

        log.info(
            "LLM request details.",
            extra={
                "response_format": request.response_format,
                "messages": [
                    {
                        "role": message.role.value,
                        "content": message.content,
                    }
                    for message in request.messages
                ],
            },
        )

        try:
            response = await self._client.chat(
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
                    ResponseError: lambda e: ClientProviderError(
                        message=str(e),
                    ),
                    TimeoutError: lambda _: ClientTimeoutError(),
                    ConnectionError: lambda _: ClientConnectionError(),
                },
                default=lambda e: ClientProviderError(
                    message=str(e),
                ),
            ) from exc

        content = response.message.content

        if not content or not content.strip():
            log.error(
                "Provider '%s' returned an empty completion.",
                self.provider,
                extra={
                    "model": self.model,
                },
            )

            raise ClientProviderError(
                message=(f"Provider '{self.provider}' " "returned an empty completion."),
            )

        log.info(
            "Generated completion using provider '%s'.",
            self.provider,
        )

        return LLMResponseDTO(
            content=content,
            provider=self.provider,
            model=self.model,
            finish_reason=None,
            usage=(
                LLMTokenUsageDTO(
                    prompt_tokens=response.prompt_eval_count or 0,
                    completion_tokens=response.eval_count or 0,
                    total_tokens=((response.prompt_eval_count or 0) + (response.eval_count or 0)),
                )
                if (response.prompt_eval_count is not None or response.eval_count is not None)
                else None
            ),
            metadata={
                "done_reason": response.done_reason,
            },
        )

    async def stream(
        self,
        *,
        request: LLMRequestDTO,
    ) -> AsyncIterator[LLMStreamChunkDTO]:
        """
        Stream a completion using the local LLM.
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
            "stream": True,
            "think": self._think,
        }

        options: dict[str, Any] = {}

        if request.temperature is not None:
            options["temperature"] = request.temperature

        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens

        if options:
            request_kwargs["options"] = options

        if request.response_format is not None:
            request_kwargs["format"] = self._to_response_format(
                request.response_format,
            )

        try:
            stream = await self._client.chat(
                **request_kwargs,
            )

            async for chunk in stream:
                content = chunk.message.content or ""

                done = bool(chunk.done)

                if done:
                    log.info(
                        "Completed streamed response using provider '%s'.",
                        self.provider,
                    )

                yield LLMStreamChunkDTO(
                    content=content,
                    is_final=done,
                    finish_reason=chunk.done_reason if done else None,
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
                    ResponseError: lambda e: ClientProviderError(
                        message=str(e),
                    ),
                    TimeoutError: lambda _: ClientTimeoutError(),
                    ConnectionError: lambda _: ClientConnectionError(),
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
        the Ollama message format.
        """

        return [
            {
                "role": message.role.value,
                "content": message.content,
            }
            for message in messages
        ]

    @staticmethod
    def _to_response_format(
        response_format: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Convert the provider-independent response format into
        Ollama's expected format.

        Ollama accepts a JSON schema directly for structured output,
        whereas the generic LLM request uses the OpenAI-style
        json_schema wrapper.
        """

        if response_format.get("type") != "json_schema":
            return response_format

        json_schema = response_format.get("json_schema")

        if not isinstance(json_schema, dict):
            return response_format

        schema = json_schema.get("schema")

        if schema is None:
            return response_format

        return schema
