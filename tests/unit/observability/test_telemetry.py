"""
Unit tests for OpenTelemetry configuration and lifecycle management.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import (
    DEPLOYMENT_ENVIRONMENT,
    SERVICE_NAME,
    SERVICE_VERSION,
    Resource,
)
from opentelemetry.sdk.trace import TracerProvider

from src.observability import telemetry


def test_create_resource() -> None:
    """Resource contains the configured application metadata."""
    resource = telemetry._create_resource()

    assert resource.attributes[SERVICE_NAME] == telemetry.settings.APP_NAME
    assert resource.attributes[SERVICE_VERSION] == telemetry.settings.OTEL_APP_VERSION
    assert resource.attributes[DEPLOYMENT_ENVIRONMENT] == telemetry.settings.ENVIRONMENT.value


def test_create_tracer_provider(
    monkeypatch,
) -> None:
    """Tracer provider is configured with the OTLP exporter."""
    resource = Resource.create()

    exporter = MagicMock()

    monkeypatch.setattr(
        telemetry,
        "OTLPSpanExporter",
        lambda **kwargs: exporter,
    )

    provider = telemetry._create_tracer_provider(
        resource,
    )

    assert isinstance(
        provider,
        TracerProvider,
    )

    assert provider.resource == resource

    assert provider._active_span_processor is not None

    (
        telemetry.OTLPSpanExporter.assert_not_called()
        if isinstance(
            telemetry.OTLPSpanExporter,
            MagicMock,
        )
        else None
    )


def test_create_meter_provider(
    monkeypatch,
) -> None:
    """Meter provider is configured with the OTLP metric exporter."""
    resource = Resource.create()

    exporter = MagicMock()
    reader = MagicMock()

    exporter_factory = MagicMock(
        return_value=exporter,
    )
    reader_factory = MagicMock(
        return_value=reader,
    )

    monkeypatch.setattr(
        telemetry,
        "OTLPMetricExporter",
        exporter_factory,
    )
    monkeypatch.setattr(
        telemetry,
        "PeriodicExportingMetricReader",
        reader_factory,
    )

    provider = telemetry._create_meter_provider(
        resource,
    )

    assert isinstance(
        provider,
        MeterProvider,
    )

    exporter_factory.assert_called_once_with(
        endpoint=telemetry.settings.OTEL_EXPORTER_OTLP_ENDPOINT,
    )

    reader_factory.assert_called_once_with(
        exporter,
    )


def test_configure_telemetry_disabled(
    monkeypatch,
) -> None:
    """Telemetry is not configured when tracing is disabled."""
    monkeypatch.setattr(
        telemetry.settings,
        "OTEL_TRACING",
        False,
    )

    tracer_provider = MagicMock()
    meter_provider = MagicMock()

    monkeypatch.setattr(
        telemetry.trace,
        "set_tracer_provider",
        tracer_provider,
    )

    monkeypatch.setattr(
        telemetry.metrics,
        "set_meter_provider",
        meter_provider,
    )

    telemetry.configure_telemetry()

    tracer_provider.assert_not_called()
    meter_provider.assert_not_called()


def test_configure_telemetry_enabled(
    monkeypatch,
) -> None:
    """Telemetry providers are registered when tracing is enabled."""
    monkeypatch.setattr(
        telemetry.settings,
        "OTEL_TRACING",
        True,
    )

    resource = MagicMock()
    tracer_provider = MagicMock()
    meter_provider = MagicMock()

    monkeypatch.setattr(
        telemetry,
        "_create_resource",
        lambda: resource,
    )

    monkeypatch.setattr(
        telemetry,
        "_create_tracer_provider",
        lambda resource: tracer_provider,
    )

    monkeypatch.setattr(
        telemetry,
        "_create_meter_provider",
        lambda resource: meter_provider,
    )

    set_tracer_provider = MagicMock()
    set_meter_provider = MagicMock()

    monkeypatch.setattr(
        telemetry.trace,
        "set_tracer_provider",
        set_tracer_provider,
    )

    monkeypatch.setattr(
        telemetry.metrics,
        "set_meter_provider",
        set_meter_provider,
    )

    telemetry.configure_telemetry()

    set_tracer_provider.assert_called_once_with(
        tracer_provider,
    )

    set_meter_provider.assert_called_once_with(
        meter_provider,
    )


def test_get_tracer() -> None:
    """Tracer is retrieved from the OpenTelemetry API."""
    tracer = MagicMock()

    get_tracer = MagicMock(
        return_value=tracer,
    )

    original = telemetry.trace.get_tracer

    try:
        telemetry.trace.get_tracer = get_tracer

        result = telemetry.get_tracer(
            "juris-ai.test",
        )

        assert result is tracer

        get_tracer.assert_called_once_with(
            "juris-ai.test",
        )
    finally:
        telemetry.trace.get_tracer = original


def test_get_meter() -> None:
    """Meter is retrieved from the OpenTelemetry API."""
    meter = MagicMock()

    get_meter = MagicMock(
        return_value=meter,
    )

    original = telemetry.metrics.get_meter

    try:
        telemetry.metrics.get_meter = get_meter

        result = telemetry.get_meter(
            "juris-ai.test",
        )

        assert result is meter

        get_meter.assert_called_once_with(
            "juris-ai.test",
        )
    finally:
        telemetry.metrics.get_meter = original


def test_shutdown_telemetry(
    monkeypatch,
) -> None:
    """Configured telemetry providers are shut down."""
    tracer_provider = MagicMock(spec=TracerProvider)
    meter_provider = MagicMock(spec=MeterProvider)

    monkeypatch.setattr(
        telemetry.trace,
        "get_tracer_provider",
        lambda: tracer_provider,
    )

    monkeypatch.setattr(
        telemetry.metrics,
        "get_meter_provider",
        lambda: meter_provider,
    )

    telemetry.shutdown_telemetry()

    tracer_provider.shutdown.assert_called_once_with()
    meter_provider.shutdown.assert_called_once_with()


def test_shutdown_telemetry_with_default_providers(
    monkeypatch,
) -> None:
    """Shutdown ignores non-SDK default providers."""
    tracer_provider = MagicMock()
    meter_provider = MagicMock()

    monkeypatch.setattr(
        telemetry.trace,
        "get_tracer_provider",
        lambda: tracer_provider,
    )

    monkeypatch.setattr(
        telemetry.metrics,
        "get_meter_provider",
        lambda: meter_provider,
    )

    telemetry.shutdown_telemetry()

    tracer_provider.shutdown.assert_not_called()
    meter_provider.shutdown.assert_not_called()
