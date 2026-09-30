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

        self.retrieval_searches: Counter = meter.create_counter(
            name="juris_ai_retrieval_searches_total",
            description=(
                "Hybrid retrieval searches, labeled by the mode they ran in "
                "(full|no_rerank|keyword_only|vector_only|unavailable)."
            ),
            unit="1",
        )

        self.llm_failovers: Counter = meter.create_counter(
            name="juris_ai_llm_failovers_total",
            description=(
                "Calls a primary LLM provider couldn't serve, labeled by "
                "primary/fallback provider, reason (error type) and outcome "
                "(attempted|skipped_context|skipped_deadline|failed)."
            ),
            unit="1",
        )

        self.failover_answers_discarded: Counter = meter.create_counter(
            name="juris_ai_failover_answers_discarded_total",
            description=(
                "Answers the local failover model produced that a Groq-only "
                "judge couldn't check and so discarded, labeled by judge "
                "(harmful_content|groundedness)."
            ),
            unit="1",
        )

        self.answer_retries_skipped: Counter = meter.create_counter(
            name="juris_ai_answer_retries_skipped_total",
            description=(
                "Answers the quality gate rejected without its usual retry "
                "(corrective retrieval and re-ask), labeled by reason "
                "(judge_provider_unavailable)."
            ),
            unit="1",
        )

        self.token_quota_rejections: Counter = meter.create_counter(
            name="juris_ai_token_quota_rejections_total",
            description=(
                "Chat requests refused by a token quota, labeled by quota " "(per_request|daily)."
            ),
            unit="1",
        )

        self.token_quota_threshold_crossings: Counter = meter.create_counter(
            name="juris_ai_token_quota_threshold_crossings_total",
            description=(
                "Users whose day's tokens crossed a fraction of the daily "
                "quota, labeled by threshold (0.8)."
            ),
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

    def record_llm_failover(
        self,
        *,
        primary: str,
        fallback: str,
        reason: str,
        outcome: Literal["attempted", "skipped_context", "skipped_deadline", "failed"],
    ) -> None:
        """
        Record one call the primary LLM provider couldn't serve.

        "attempted" is recorded when the fallback call starts, so a
        "failed" count (error or deadline reached) is a subset of it, not
        in addition.
        """

        self.llm_failovers.add(
            1,
            attributes={
                "primary": primary,
                "fallback": fallback,
                "reason": reason,
                "outcome": outcome,
            },
        )

    def record_retrieval(self, *, mode: str) -> None:
        """
        Record one hybrid retrieval search and the mode it ran in: full,
        or degraded because a component failed (review R4).
        """

        self.retrieval_searches.add(1, attributes={"mode": mode})

    def record_failover_answer_discarded(
        self,
        *,
        judge: Literal["harmful_content", "groundedness"],
    ) -> None:
        """
        Record an answer from the local failover model that a Groq-only
        judge couldn't check (Groq down), so it was refused or marked
        unverified (review R17: judges deliberately don't fail over).
        """

        self.failover_answers_discarded.add(1, attributes={"judge": judge})

    def record_answer_retry_skipped(
        self,
        *,
        reason: Literal["judge_provider_unavailable"],
    ) -> None:
        """
        Record an answer the quality gate rejected without retrying: the
        groundedness judge's provider was down, so a re-asked answer
        couldn't be checked either (review R17).
        """

        self.answer_retries_skipped.add(1, attributes={"reason": reason})

    def record_token_quota_rejection(
        self,
        *,
        quota: Literal["per_request", "daily"],
    ) -> None:
        """Record a chat request refused by a token quota."""

        self.token_quota_rejections.add(1, attributes={"quota": quota})

    def record_token_quota_threshold_crossed(
        self,
        *,
        threshold: Literal["0.8"],
    ) -> None:
        """Record a user's day's tokens crossing a fraction of the daily quota."""

        self.token_quota_threshold_crossings.add(1, attributes={"threshold": threshold})


metrics = ApplicationMetrics()
