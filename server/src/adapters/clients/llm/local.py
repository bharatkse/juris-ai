"""
Local LLM client.

Provides an LLMClient implementation for local LLM inference
through Ollama.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

try:
    from ollama import AsyncClient, ResponseError
except ImportError:  # pragma: no cover - optional in incomplete local images
    AsyncClient = None

    class ResponseError(Exception):
        status_code: int | None = None

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

# Qwen3's published native window. Not requested as Ollama num_ctx on
# typical Docker Desktop VMs: 32k KV cache is ~4.5 GiB on qwen3:8b,
# which plus ~5 GiB weights is SIGKILL'd inside an 8 GiB VM.
QWEN3_NATIVE_CTX = 32_768

# Default Ollama allocation for qwen3:4b / qwen3:8b. token_budget.py
# imports this same constant so prompt budgets match what is requested.
QWEN3_NUM_CTX = 4_096
LOCAL_DEFAULT_NUM_PREDICT = 1_024


class LocalLLMClient(LLMClient):
    """
    Local LLM implementation using Ollama.
    """

    def __init__(
        self,
        *,
        base_url: str | None,
        model: str,
        num_ctx: int = QWEN3_NUM_CTX,
    ) -> None:
        if AsyncClient is None:
            raise ClientProviderError(
                "The ollama package is not installed.",
            )

        self._client = AsyncClient(
            host=base_url,
        )
        self._base_url = base_url
        self._model = model
        self._num_ctx = num_ctx
        self._think = False

        log.info(
            "Initialized local LLM client with Ollama. "
            "Base URL: '%s', model: '%s', num_ctx: %s.",
            base_url,
            model,
            num_ctx,
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

    async def _generate(
        self,
        *,
        request: LLMRequestDTO,
    ) -> LLMResponseDTO:
        """
        Generate a completion using the local LLM. Called by
        LLMClient.generate(), which wraps this with call-duration/
        token metrics -- see that method's docstring.
        """

        log.info(
            "Generating completion using provider '%s', model '%s'.",
            self.provider,
            self.model,
        )

        inference = request.inference
        model = inference.model or self._model

        request_kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._to_messages(
                request.messages,
            ),
            "think": self._think,
        }

        options: dict[str, Any] = {
            "temperature": inference.temperature,
            "num_ctx": self._num_ctx,
        }

        if inference.top_p is not None:
            options["top_p"] = inference.top_p

        options["num_predict"] = (
            inference.max_output_tokens or LOCAL_DEFAULT_NUM_PREDICT
        )

        if options:
            request_kwargs["options"] = options

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
                "message_count": len(request.messages),
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
                    ResponseError: lambda e: self._provider_error(e),
                    TimeoutError: lambda _: ClientTimeoutError(),
                    ConnectionError: lambda _: ClientConnectionError(
                        message=(
                            f"Cannot reach Ollama at {self._base_url}. "
                            "Start the Ollama service, or set GROQ_API_KEY in .env."
                        ),
                    ),
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
            model=model,
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

        inference = request.inference
        model = inference.model or self._model

        request_kwargs: dict[str, Any] = {
            "model": model,
            "messages": self._to_messages(
                request.messages,
            ),
            "stream": True,
            "think": self._think,
        }

        options: dict[str, Any] = {
            "temperature": inference.temperature,
            "num_ctx": self._num_ctx,
        }

        if inference.top_p is not None:
            options["top_p"] = inference.top_p

        options["num_predict"] = (
            inference.max_output_tokens or LOCAL_DEFAULT_NUM_PREDICT
        )

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
                    ResponseError: lambda e: self._provider_error(e),
                    TimeoutError: lambda _: ClientTimeoutError(),
                    ConnectionError: lambda _: ClientConnectionError(
                        message=(
                            f"Cannot reach Ollama at {self._base_url}. "
                            "Start the Ollama service, or set GROQ_API_KEY in .env."
                        ),
                    ),
                },
                default=lambda e: ClientProviderError(
                    message=str(e),
                ),
            ) from exc

    def _provider_error(self, exc: Exception) -> ClientProviderError:
        status_code = getattr(exc, "status_code", None)
        text = str(exc)
        if status_code == 404 or "not found" in text.lower():
            return ClientProviderError(
                message=(
                    f"Ollama does not have {self._model} yet. "
                    f"Pull it with `ollama pull {self._model}`, "
                    "or set GROQ_API_KEY in .env."
                ),
            )
        if "killed" in text.lower():
            return ClientProviderError(
                message=(
                    f"Ollama ran out of memory loading {self._model} "
                    f"(num_ctx={self._num_ctx}). Lower LLM_LOCAL_NUM_CTX "
                    "or give Docker more RAM."
                ),
            )
        return ClientProviderError(message=text)

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

        if not isinstance(schema, dict):
            return response_format

        return schema
