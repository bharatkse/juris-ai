"""
Unit tests for application metrics.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from adapters.observability.metrics import ApplicationMetrics
from core.dto.clients.llm import LLMTokenUsageDTO


def test_application_metrics_creates_instruments(
    monkeypatch,
) -> None:
    """Application metrics create the expected instruments."""
    meter = MagicMock()

    monkeypatch.setattr(
        "adapters.observability.metrics.get_meter",
        lambda _: meter,
    )

    ApplicationMetrics()

    meter.create_counter.assert_any_call(
        name="juris_ai_health_checks",
        description="Number of health checks.",
        unit="1",
    )

    meter.create_counter.assert_any_call(
        name="juris_ai_cache_requests_total",
        description=(
            "Cache lookups, labeled by result (hit|miss) and which cache " "(embedding|judge)."
        ),
        unit="1",
    )

    meter.create_counter.assert_any_call(
        name="juris_ai_llm_tokens_total",
        description=("LLM tokens consumed, labeled by provider/model/type (input|output)."),
        unit="1",
    )

    meter.create_histogram.assert_any_call(
        name="juris_ai_llm_call_duration_seconds",
        description="LLMClient.generate() call duration, labeled by provider/model.",
        unit="s",
    )


def test_increment_health_checks() -> None:
    """Health check counter is incremented by one."""
    metrics = ApplicationMetrics()

    metrics.health_checks = MagicMock()

    attributes = {
        "endpoint": "/health",
        "status": "success",
    }

    metrics.increment_health_checks(
        attributes=attributes,
    )

    metrics.health_checks.add.assert_called_once_with(
        1,
        attributes=attributes,
    )


def test_increment_health_checks_without_attributes() -> None:
    """Health check counter supports calls without attributes."""
    metrics = ApplicationMetrics()

    metrics.health_checks = MagicMock()

    metrics.increment_health_checks()

    metrics.health_checks.add.assert_called_once_with(
        1,
        attributes=None,
    )


def test_record_cache_request_hit() -> None:
    """A cache hit is recorded with result='hit' and the given cache label."""
    metrics = ApplicationMetrics()

    metrics.cache_requests = MagicMock()

    metrics.record_cache_request(result="hit", cache="embedding")

    metrics.cache_requests.add.assert_called_once_with(
        1,
        attributes={"result": "hit", "cache": "embedding"},
    )


def test_record_cache_request_miss_with_count() -> None:
    """A batch miss records the given count, not a fixed 1."""
    metrics = ApplicationMetrics()

    metrics.cache_requests = MagicMock()

    metrics.record_cache_request(result="miss", cache="judge", count=5)

    metrics.cache_requests.add.assert_called_once_with(
        5,
        attributes={"result": "miss", "cache": "judge"},
    )


def test_record_cache_unavailable() -> None:
    """A cache backend failure (or a lookup skipped after one) is counted (review R23)."""
    metrics = ApplicationMetrics()

    metrics.cache_unavailable = MagicMock()

    metrics.record_cache_unavailable(
        backend="redis", cache="embedding", operation="get", outcome="error"
    )

    metrics.cache_unavailable.add.assert_called_once_with(
        1,
        attributes={
            "backend": "redis",
            "cache": "embedding",
            "operation": "get",
            "outcome": "error",
        },
    )


def test_cache_unavailable_counter_is_created(monkeypatch) -> None:
    meter = MagicMock()
    monkeypatch.setattr("adapters.observability.metrics.get_meter", lambda _: meter)

    ApplicationMetrics()

    names = [call.kwargs["name"] for call in meter.create_counter.call_args_list]
    assert "juris_ai_cache_unavailable_total" in names


def test_agent_decision_metrics_are_recorded() -> None:
    """Decision, rejection, execution and fallback counts (review M1)."""
    metrics = ApplicationMetrics()
    for name in (
        "agent_decisions",
        "agent_rejected_decisions",
        "agent_executions",
        "agent_execution_tool_calls",
        "agent_execution_llm_calls",
        "orchestration_fallbacks",
    ):
        setattr(metrics, name, MagicMock())

    metrics.record_agent_decision(agent="legal", decision_type="final")
    metrics.record_rejected_decision(agent="legal", cause="parse_failure")
    metrics.record_agent_execution(
        agent="legal", termination="completed", tool_calls=2, llm_calls=3
    )
    metrics.record_orchestration_fallback(reason="no_agent_response")

    metrics.agent_decisions.add.assert_called_once_with(
        1, attributes={"agent": "legal", "decision_type": "final"}
    )
    metrics.agent_rejected_decisions.add.assert_called_once_with(
        1, attributes={"agent": "legal", "cause": "parse_failure"}
    )
    metrics.agent_executions.add.assert_called_once_with(
        1, attributes={"agent": "legal", "termination": "completed"}
    )
    metrics.agent_execution_tool_calls.record.assert_called_once_with(
        2, attributes={"agent": "legal"}
    )
    metrics.agent_execution_llm_calls.record.assert_called_once_with(
        3, attributes={"agent": "legal"}
    )
    metrics.orchestration_fallbacks.add.assert_called_once_with(
        1, attributes={"reason": "no_agent_response"}
    )


def test_record_llm_call_with_usage() -> None:
    """Duration is always recorded; token counts are recorded when usage is present."""
    metrics = ApplicationMetrics()

    metrics.llm_call_duration = MagicMock()
    metrics.llm_tokens = MagicMock()

    metrics.record_llm_call(
        provider="groq",
        model="llama-3.3-70b",
        duration=1.5,
        usage=LLMTokenUsageDTO(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
        ),
    )

    metrics.llm_call_duration.record.assert_called_once_with(
        1.5,
        attributes={"provider": "groq", "model": "llama-3.3-70b"},
    )

    metrics.llm_tokens.add.assert_any_call(
        100,
        attributes={"provider": "groq", "model": "llama-3.3-70b", "type": "input"},
    )
    metrics.llm_tokens.add.assert_any_call(
        50,
        attributes={"provider": "groq", "model": "llama-3.3-70b", "type": "output"},
    )


def test_record_llm_call_without_usage() -> None:
    """No usage -- duration is still recorded, but no token counts."""
    metrics = ApplicationMetrics()

    metrics.llm_call_duration = MagicMock()
    metrics.llm_tokens = MagicMock()

    metrics.record_llm_call(
        provider="local",
        model="qwen3:8b",
        duration=0.8,
        usage=None,
    )

    metrics.llm_call_duration.record.assert_called_once_with(
        0.8,
        attributes={"provider": "local", "model": "qwen3:8b"},
    )

    metrics.llm_tokens.add.assert_not_called()
