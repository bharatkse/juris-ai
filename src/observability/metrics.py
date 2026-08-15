"""
Application metrics.
"""

from __future__ import annotations

from typing import Any

from opentelemetry.metrics import Counter, Histogram

from src.observability.telemetry import get_meter


class ApplicationMetrics:
    """Application-level OpenTelemetry metrics."""

    def __init__(self) -> None:
        """Initialize application metrics."""

        meter = get_meter("juris-ai.application")

        self.health_checks: Counter = meter.create_counter(
            name="juris_ai_health_checks",
            description="Number of health checks.",
            unit="1",
        )

        self.request_duration: Histogram = meter.create_histogram(
            name="juris_ai_request_duration",
            description="Application request duration.",
            unit="s",
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

    def record_request_duration(
        self,
        duration: float,
        *,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Record application request duration."""

        self.request_duration.record(
            duration,
            attributes=attributes,
        )


metrics = ApplicationMetrics()
