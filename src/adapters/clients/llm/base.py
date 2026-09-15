"""
Base LLM client.

Defines the interface implemented by all LLM providers.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import replace
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from adapters.observability.logger import get_logger
from adapters.observability.metrics import metrics
from core.dto.clients.llm import LLMRequestDTO, LLMResponseDTO, LLMStreamChunkDTO
from core.exceptions.client import ClientProviderError

log = get_logger(__name__)

T = TypeVar(
    "T",
    bound=BaseModel,
)


class LLMClient(ABC):
    """
    Base class for all LLM providers.

    Implementations must be stateless and safe for concurrent use.
    """

    @property
    @abstractmethod
    def provider(
        self,
    ) -> str:
        """
        Return the provider name.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def model(
        self,
    ) -> str:
        """
        Return the configured model name.
        """
        raise NotImplementedError

    async def generate(
        self,
        *,
        request: LLMRequestDTO,
    ) -> LLMResponseDTO:
        """
        Generate a text completion.

        Concrete, not abstract: wraps each provider's _generate() with
        call-duration and token-usage instrumentation (juris_ai_llm_call_duration_seconds,
        juris_ai_llm_tokens_total) so every provider gets it once, here,
        rather than each duplicating the same timing code around its
        own _generate(). generate_structured() below calls this
        method (not _generate() directly), so structured calls are
        covered too. stream() is not instrumented the same way --
        LLMStreamChunkDTO carries no usage data, and "duration" means
        something different for a stream (time to first chunk vs.
        total time), so it's left out rather than given a
        half-meaningful number.
        """

        start = time.perf_counter()
        response: LLMResponseDTO | None = None

        try:
            response = await self._generate(
                request=request,
            )

            return response

        finally:
            # response.provider/response.model, not self.provider/
            # self.model, when available: request.inference.model can
            # override the client's own default model per-call (see
            # wiring/factories/evaluation.py::build_llm_judge(), which
            # always does this) -- self.model would misreport which
            # model an overridden call actually used. Only fall back
            # to the client's own identity when _generate() raised
            # before producing a response to read it from.
            metrics.record_llm_call(
                provider=response.provider if response is not None else self.provider,
                model=response.model if response is not None else self.model,
                duration=time.perf_counter() - start,
                usage=response.usage if response is not None else None,
            )

    @abstractmethod
    async def _generate(
        self,
        *,
        request: LLMRequestDTO,
    ) -> LLMResponseDTO:
        """
        Provider-specific completion generation. Called by generate()
        above, which is what every caller should actually invoke --
        this method exists so instrumentation lives in exactly one
        place (generate()) rather than being duplicated in every
        provider implementation.
        """
        raise NotImplementedError

    async def generate_structured(
        self,
        *,
        request: LLMRequestDTO,
        response_model: type[T],
    ) -> T:
        """
        Generate and validate a structured response.
        """

        log.debug(
            "Generating structured response using provider '%s', "
            "model '%s', response_model='%s'.",
            self.provider,
            self.model,
            response_model.__name__,
        )

        structured_request = replace(
            request,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "schema": response_model.model_json_schema(),
                },
            },
        )

        response = await self.generate(
            request=structured_request,
        )

        try:
            result = response_model.model_validate_json(
                response.content,
            )

        except ValidationError as exc:
            log.exception(
                "Failed to validate structured response using '%s'. " "Provider='%s', model='%s'.",
                response_model.__name__,
                self.provider,
                self.model,
            )

            raise ClientProviderError(
                message="LLM returned an invalid structured response.",
            ) from exc

        log.debug(
            "Successfully validated structured response using '%s'.",
            response_model.__name__,
        )

        return result

    @abstractmethod
    async def stream(
        self,
        *,
        request: LLMRequestDTO,
    ) -> AsyncIterator[LLMStreamChunkDTO]:
        """
        Stream a completion.
        """
        raise NotImplementedError
