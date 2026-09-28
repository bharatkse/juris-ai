"""
Failover LLM client.

Sends each call to a primary client (Groq) and, when the primary is
unavailable, repeats the same call on a fallback client (local Ollama)
instead of failing the request.

What counts as "unavailable" (FAILOVER_ERRORS): the provider couldn't
answer at all -- rate limit (after the SDK's own retries), timeout,
connection failure, or a 5xx. Everything else still fails the call:
authentication and configuration errors (a deployment problem the
fallback would only hide), a 4xx the provider rejected the request with,
and a response that arrived but couldn't be used (empty, or not valid
for the response schema) -- the request itself is the problem there, not
the provider's availability.

The fallback gets the same messages and response schema. Two things
change: the request's model override is cleared (a Groq model name means
nothing to Ollama, which uses its own configured model), and the call is
skipped when the prompt doesn't fit the fallback's smaller context
window (``fits_fallback``), because Ollama would otherwise silently cut
the start of the prompt -- the system prompt -- instead of failing. When
the fallback is skipped or also fails, the primary's error is raised.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import replace

from adapters.clients.llm.base import LLMClient
from adapters.observability.logger import get_logger
from adapters.observability.metrics import metrics
from core.dto.clients.llm import LLMRequestDTO, LLMResponseDTO, LLMStreamChunkDTO
from core.exceptions.client import (
    ClientConnectionError,
    ClientError,
    ClientRateLimitError,
    ClientServiceUnavailableError,
    ClientTimeoutError,
)

log = get_logger(__name__)

FAILOVER_ERRORS: tuple[type[ClientError], ...] = (
    ClientRateLimitError,
    ClientTimeoutError,
    ClientConnectionError,
    ClientServiceUnavailableError,
)


class FailoverLLMClient(LLMClient):
    """
    Primary client with a fallback for provider outages.

    Reports the primary's provider and model: prompts are built for the
    primary, and ``fits_fallback`` decides per call whether one can also
    go to the fallback.
    """

    def __init__(
        self,
        *,
        primary: LLMClient,
        fallback: LLMClient,
        fits_fallback: Callable[[LLMRequestDTO], bool],
    ) -> None:
        self._primary = primary
        self._fallback = fallback
        self._fits_fallback = fits_fallback

    @property
    def provider(
        self,
    ) -> str:
        return self._primary.provider

    @property
    def model(
        self,
    ) -> str:
        return self._primary.model

    async def generate(
        self,
        *,
        request: LLMRequestDTO,
    ) -> LLMResponseDTO:
        """
        Generate with the primary, or the fallback when the primary is
        unavailable.

        Overrides LLMClient.generate() rather than _generate(): each
        underlying client's own generate() already records call metrics
        under its real provider and model, so this adds none of its own.
        """

        try:
            return await self._primary.generate(
                request=request,
            )

        except FAILOVER_ERRORS as exc:
            fallback_request = self._fallback_request(
                request=request,
                error=exc,
            )

            if fallback_request is None:
                raise

            try:
                return await self._fallback.generate(
                    request=fallback_request,
                )

            except ClientError as fallback_exc:
                metrics.record_llm_failover(
                    primary=self._primary.provider,
                    fallback=self._fallback.provider,
                    reason=type(exc).__name__,
                    outcome="failed",
                )
                log.error(
                    "Fallback provider '%s' also failed (%s); raising the "
                    "primary provider's error.",
                    self._fallback.provider,
                    type(fallback_exc).__name__,
                )
                raise exc from None

    async def _generate(
        self,
        *,
        request: LLMRequestDTO,
    ) -> LLMResponseDTO:
        # Unused: generate() is overridden. Kept for the abstract contract.
        return await self.generate(
            request=request,
        )

    async def stream(
        self,
        *,
        request: LLMRequestDTO,
    ) -> AsyncIterator[LLMStreamChunkDTO]:
        """
        Stream from the primary; fail over only if it fails before the
        first chunk (a half-streamed answer can't be continued elsewhere).
        """

        started = False

        try:
            async for chunk in self._primary.stream(
                request=request,
            ):
                started = True
                yield chunk

        except FAILOVER_ERRORS as exc:
            if started:
                raise

            fallback_request = self._fallback_request(
                request=request,
                error=exc,
            )

            if fallback_request is None:
                raise

            async for chunk in self._fallback.stream(
                request=fallback_request,
            ):
                yield chunk

    def _fallback_request(
        self,
        *,
        request: LLMRequestDTO,
        error: ClientError,
    ) -> LLMRequestDTO | None:
        """
        The request to send to the fallback, or None when it can't take it.
        """

        reason = type(error).__name__

        if not self._fits_fallback(request):
            metrics.record_llm_failover(
                primary=self._primary.provider,
                fallback=self._fallback.provider,
                reason=reason,
                outcome="skipped_context",
            )
            log.warning(
                "Primary provider '%s' unavailable (%s), but the prompt "
                "doesn't fit fallback provider '%s''s context window; not "
                "failing over.",
                self._primary.provider,
                reason,
                self._fallback.provider,
            )
            return None

        metrics.record_llm_failover(
            primary=self._primary.provider,
            fallback=self._fallback.provider,
            reason=reason,
            outcome="attempted",
        )
        log.warning(
            "Primary provider '%s' unavailable (%s); failing over to '%s' " "(model '%s').",
            self._primary.provider,
            reason,
            self._fallback.provider,
            self._fallback.model,
        )

        return replace(
            request,
            inference=replace(
                request.inference,
                model=None,
            ),
        )
