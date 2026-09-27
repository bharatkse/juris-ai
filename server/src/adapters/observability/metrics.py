"""
Application metrics.
"""

from __future__ import annotations

from typing import Any, Literal

from opentelemetry.metrics import Counter, Histogram

from adapters.observability.telemetry import get_meter
from core.dto.clients.llm import LLMTokenUsageDTO


class ApplicationMetrics:
    """Application-level OpenTelemetry metrics."""

    def __init__(self) -> None:
        """Initialize application metrics."""

        meter = get_meter("juris-agentic.application")

        self.health_checks: Counter = meter.create_counter(
            name="juris_ai_health_checks",
            description="Number of health checks.",
            unit="1",
        )

        self.cache_requests: Counter = meter.create_counter(
            name="juris_ai_cache_requests_total",
            description=(
                "Cache lookups, labeled by result (hit|miss) and which cache " "(embedding|judge)."
            ),
            unit="1",
        )

        self.llm_call_duration: Histogram = meter.create_histogram(
            name="juris_ai_llm_call_duration_seconds",
            description="LLMClient.generate() call duration, labeled by provider/model.",
            unit="s",
        )

        self.llm_tokens: Counter = meter.create_counter(
            name="juris_ai_llm_tokens_total",
            description=("LLM tokens consumed, labeled by provider/model/type (input|output)."),
            unit="1",
        )

    def increment_health_checks(
        self,
        *,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Increment the health check counter."""

        self.health_checks.add(
            1,
            attributes=attributes,
        )

    def record_cache_request(
        self,
        *,
        result: Literal["hit", "miss"],
        cache: str,
        count: int = 1,
    ) -> None:
        """
        Record cache lookup outcome(s).

        `count` lets a batch lookup (e.g.
        CachingEmbeddingProvider.embed(), which checks one cache entry
        per text in a batch) record its hits/misses in two calls total
        rather than looping once per text.
        """

        self.cache_requests.add(
            count,
            attributes={
                "result": result,
                "cache": cache,
            },
        )

    def record_llm_call(
        self,
        *,
        provider: str,
        model: str,
        duration: float,
        usage: LLMTokenUsageDTO | None,
    ) -> None:
        """
        Record one LLMClient.generate() call's duration and (when the
        provider reported it) token usage.

        usage is Optional because LLMResponseDTO.usage itself is --
        not every provider/response guarantees token counts.
        """

        attributes = {
            "provider": provider,
            "model": model,
        }

        self.llm_call_duration.record(
            duration,
            attributes=attributes,
        )

        if usage is not None:
            self.llm_tokens.add(
                usage.prompt_tokens,
                attributes={**attributes, "type": "input"},
            )
            self.llm_tokens.add(
                usage.completion_tokens,
                attributes={**attributes, "type": "output"},
            )


metrics = ApplicationMetrics()
