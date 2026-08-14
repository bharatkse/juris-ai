"""
Application tracing helpers.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

from src.observability.telemetry import get_tracer


def get_application_tracer() -> trace.Tracer:
    """
    Return the application tracer.
    """

    return get_tracer(
        "juris-ai.application",
    )


@contextmanager
def span(
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
) -> Generator[Span]:
    """
    Create an application span.
    """

    tracer = get_application_tracer()

    with tracer.start_as_current_span(
        name,
    ) as current_span:
        if attributes:
            set_span_attributes(
                current_span,
                attributes,
            )

        try:
            yield current_span

        except Exception as exc:
            record_exception(
                current_span,
                exc,
            )
            raise


def _normalize_attributes(
    attributes: dict[str, Any],
) -> dict[str, str | int | float | bool]:
    """
    Normalize span attributes to OpenTelemetry-compatible values.
    """

    normalized: dict[str, str | int | float | bool] = {}

    for key, value in attributes.items():
        if value is None:
            continue

        if isinstance(
            value,
            str | int | float | bool,
        ):
            normalized[key] = value
        else:
            normalized[key] = str(value)

    return normalized


def set_span_attributes(
    current_span: Span,
    attributes: dict[str, Any],
) -> None:
    """
    Add attributes to a span.
    """

    for key, value in _normalize_attributes(
        attributes,
    ).items():
        current_span.set_attribute(
            key,
            value,
        )


def record_exception(
    current_span: Span,
    exception: Exception,
) -> None:
    """
    Record an exception and mark the span as failed.
    """

    current_span.record_exception(
        exception,
    )

    current_span.set_status(
        Status(
            StatusCode.ERROR,
            str(exception),
        ),
    )


def set_span_error(
    current_span: Span,
    message: str,
) -> None:
    """
    Mark a span as failed.
    """

    current_span.set_status(
        Status(
            StatusCode.ERROR,
            message,
        ),
    )


def add_span_event(
    current_span: Span,
    name: str,
    *,
    attributes: dict[str, Any] | None = None,
) -> None:
    """
    Add an event to a span.
    """

    current_span.add_event(
        name,
        attributes=(_normalize_attributes(attributes) if attributes else None),
    )
