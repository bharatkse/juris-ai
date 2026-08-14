"""
OpenTelemetry configuration and lifecycle management.
"""

from __future__ import annotations

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.metrics import Meter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import (
    DEPLOYMENT_ENVIRONMENT,
    SERVICE_NAME,
    SERVICE_VERSION,
    Resource,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from src.core.config import settings


def _create_resource() -> Resource:
    """Create OpenTelemetry resource metadata."""

    return Resource.create(
        attributes={
            SERVICE_NAME: settings.APP_NAME,
            SERVICE_VERSION: settings.OTEL_APP_VERSION,
            DEPLOYMENT_ENVIRONMENT: settings.ENVIRONMENT.value,
        },
    )


def _create_tracer_provider(
    resource: Resource,
) -> TracerProvider:
    """Create the OpenTelemetry tracer provider."""

    provider = TracerProvider(
        resource=resource,
    )

    exporter = OTLPSpanExporter(
        endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
    )

    provider.add_span_processor(
        BatchSpanProcessor(exporter),
    )

    return provider


def _create_meter_provider(
    resource: Resource,
) -> MeterProvider:
    """Create the OpenTelemetry meter provider."""

    exporter = OTLPMetricExporter(
        endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
    )

    reader = PeriodicExportingMetricReader(
        exporter,
    )

    return MeterProvider(
        resource=resource,
        metric_readers=[reader],
    )


def configure_telemetry() -> None:
    """
    Configure OpenTelemetry.

    When telemetry is disabled, OpenTelemetry remains on its
    default no-op implementation.
    """

    if not settings.OTEL_TRACING:
        return

    resource = _create_resource()

    trace.set_tracer_provider(
        _create_tracer_provider(resource),
    )

    metrics.set_meter_provider(
        _create_meter_provider(resource),
    )


def get_tracer(
    name: str,
) -> trace.Tracer:
    """Return an OpenTelemetry tracer."""

    return trace.get_tracer(name)


def get_meter(
    name: str,
) -> Meter:
    """Return an OpenTelemetry meter."""

    return metrics.get_meter(name)


def shutdown_telemetry() -> None:
    """Flush and shut down OpenTelemetry providers."""

    tracer_provider = trace.get_tracer_provider()

    if isinstance(
        tracer_provider,
        TracerProvider,
    ):
        tracer_provider.shutdown()

    meter_provider = metrics.get_meter_provider()

    if isinstance(
        meter_provider,
        MeterProvider,
    ):
        meter_provider.shutdown()
