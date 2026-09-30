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
from core.exceptions.client import ClientInvalidResponseError
from core.usage import check_request_token_quota, record_llm_usage

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

    async def warm_up(self) -> None:
        """
        Load the model ahead of the first real call (application startup).
        A no-op here for hosted providers, which have nothing to load.
        """

        return None

    async def aclose(self) -> None:
        """
        Release the client's connections (its provider SDK's HTTP client).
        Called once at application shutdown (review R17); a no-op here for
        clients that hold none.
        """

        return None

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

        Before the provider is called, the request's token quota is
        checked (core.usage): a call that would take the request past
        TOKEN_QUOTA_PER_REQUEST raises
        RequestTokenQuotaExceededError and is never made.
        """

        check_request_token_quota(message.content for message in request.messages)

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

            # The request's total, for the user's token quota
            # (core.usage; read by AIOrchestrator).
            if response is not None and response.usage is not None:
                record_llm_usage(
                    provider=response.provider,
                    model=response.model,
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    total_tokens=response.usage.total_tokens,
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

        The provider is asked for response_model's own schema. A client
        that enforces the schema while decoding may use the narrower
        request.response_schema instead (LocalLLMClient); either way the
        output is validated into response_model.
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

            raise ClientInvalidResponseError(
                message="LLM returned an invalid structured response.",
            ) from exc

        log.debug(
            "Successfully validated structured response using '%s'.",
            response_model.__name__,
        )

        return result

    @abstractmethod
    def stream(
        self,
        *,
        request: LLMRequestDTO,
    ) -> AsyncIterator[LLMStreamChunkDTO]:
        """
        Stream a completion.

        Declared without ``async`` deliberately: an ``async def``
        abstract method whose body never ``yield``s (just ``raise``s)
        is inferred by mypy as returning a plain
        ``Coroutine[..., AsyncIterator[...]]``, not an async generator
        -- which then makes every real (``async def`` + ``yield``)
        override look "incompatible" to mypy, and makes
        ``async for chunk in self._llm.stream(...)`` fail typing at
        every call site (confirmed: this broke both
        ``local.py``'s override and ``agents/base.py``'s call before
        this fix). A plain method returning ``AsyncIterator[...]`` is
        exactly what an async-generator-function call site expects,
        and concrete subclasses still implement it as
        ``async def stream(...)`` with real ``yield`` statements --
        Python itself doesn't require the abstract and concrete
        signatures to match on ``async``-ness, only mypy's shape
        inference cared.
        """
        raise NotImplementedError
