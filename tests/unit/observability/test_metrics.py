"""
Unit tests for application metrics.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.observability.metrics import ApplicationMetrics


def test_application_metrics_creates_instruments(
    monkeypatch,
) -> None:
    """Application metrics create the expected instruments."""
    meter = MagicMock()

    monkeypatch.setattr(
        "src.observability.metrics.get_meter",
        lambda _: meter,
    )

    ApplicationMetrics()

    meter.create_counter.assert_called_once_with(
        name="juris_ai_health_checks",
        description="Number of health checks.",
        unit="1",
    )

    meter.create_histogram.assert_called_once_with(
        name="juris_ai_request_duration",
        description="Application request duration.",
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


def test_record_request_duration() -> None:
    """Request duration is recorded on the histogram."""
    metrics = ApplicationMetrics()

    metrics.request_duration = MagicMock()

    attributes = {
        "method": "POST",
        "route": "/api/v1/chat",
        "status_code": 200,
    }

    metrics.record_request_duration(
        1.25,
        attributes=attributes,
    )

    metrics.request_duration.record.assert_called_once_with(
        1.25,
        attributes=attributes,
    )


def test_record_request_duration_without_attributes() -> None:
    """Request duration supports calls without attributes."""
    metrics = ApplicationMetrics()

    metrics.request_duration = MagicMock()

    metrics.record_request_duration(
        0.42,
    )

    metrics.request_duration.record.assert_called_once_with(
        0.42,
        attributes=None,
    )
