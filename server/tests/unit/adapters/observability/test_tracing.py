"""
Unit tests for application tracing helpers.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from opentelemetry.trace import StatusCode

from adapters.observability import tracing


def test_get_application_tracer(
    monkeypatch,
) -> None:
    """Return the application tracer."""
    tracer = MagicMock()

    get_tracer = MagicMock(
        return_value=tracer,
    )

    monkeypatch.setattr(
        tracing,
        "get_tracer",
        get_tracer,
    )

    result = tracing.get_application_tracer()

    assert result is tracer

    get_tracer.assert_called_once_with(
        "juris-agentic.application",
    )


def test_span_creates_span() -> None:
    """Create an application span."""
    span = MagicMock()
    tracer = MagicMock()

    tracer.start_as_current_span.return_value.__enter__.return_value = span

    original = tracing.get_application_tracer

    try:
        tracing.get_application_tracer = lambda: tracer

        with tracing.span("juris_agentic.test") as current_span:
            assert current_span is span

    finally:
        tracing.get_application_tracer = original

    tracer.start_as_current_span.assert_called_once_with(
        "juris_agentic.test",
    )


def test_span_sets_attributes() -> None:
    """Span attributes are applied when provided."""
    span = MagicMock()
    tracer = MagicMock()

    tracer.start_as_current_span.return_value.__enter__.return_value = span

    original = tracing.get_application_tracer

    try:
        tracing.get_application_tracer = lambda: tracer

        with tracing.span(
            "juris_agentic.test",
            attributes={
                "request.id": "req-123",
                "step.count": 2,
            },
        ):
            pass

    finally:
        tracing.get_application_tracer = original

    span.set_attribute.assert_any_call(
        "request.id",
        "req-123",
    )
    span.set_attribute.assert_any_call(
        "step.count",
        2,
    )


def test_span_records_exception() -> None:
    """Exceptions are recorded and re-raised."""
    span = MagicMock()
    tracer = MagicMock()

    tracer.start_as_current_span.return_value.__enter__.return_value = span

    original = tracing.get_application_tracer

    try:
        tracing.get_application_tracer = lambda: tracer

        with pytest.raises(ValueError, match="test error"):
            with tracing.span("juris_agentic.test"):
                raise ValueError("test error")

    finally:
        tracing.get_application_tracer = original

    span.record_exception.assert_called_once()

    span.set_status.assert_called_once()

    status = span.set_status.call_args.args[0]

    assert status.status_code == StatusCode.ERROR
    assert status.description == "test error"


@pytest.mark.parametrize(
    ("attributes", "expected"),
    [
        (
            {
                "string": "value",
                "integer": 10,
                "float": 1.5,
                "boolean": True,
            },
            {
                "string": "value",
                "integer": 10,
                "float": 1.5,
                "boolean": True,
            },
        ),
        (
            {
                "none": None,
                "value": "test",
            },
            {
                "value": "test",
            },
        ),
        (
            {
                "uuid": object(),
                "list": [1, 2, 3],
            },
            {},
        ),
    ],
)
def test_normalize_attributes(
    attributes,
    expected,
) -> None:
    """Normalize attributes to OpenTelemetry-compatible values."""
    normalized = tracing._normalize_attributes(
        attributes,
    )

    if "uuid" in attributes:
        assert isinstance(
            normalized["uuid"],
            str,
        )

    if "list" in attributes:
        assert isinstance(
            normalized["list"],
            str,
        )

    for key, value in expected.items():
        assert normalized[key] == value


def test_set_span_attributes() -> None:
    """Set normalized attributes on a span."""
    span = MagicMock()

    tracing.set_span_attributes(
        span,
        {
            "request.id": "req-123",
            "count": 3,
            "ignored": None,
            "object": object(),
        },
    )

    assert span.set_attribute.call_count == 3

    span.set_attribute.assert_any_call(
        "request.id",
        "req-123",
    )
    span.set_attribute.assert_any_call(
        "count",
        3,
    )
    span.set_attribute.assert_any_call(
        "object",
        pytest.approx(
            span.set_attribute.call_args_list[-1].args[1],
        ),
    )


def test_record_exception() -> None:
    """Record an exception and mark the span as failed."""
    span = MagicMock()
    exception = RuntimeError("something failed")

    tracing.record_exception(
        span,
        exception,
    )

    span.record_exception.assert_called_once_with(
        exception,
    )

    status = span.set_status.call_args.args[0]

    assert status.status_code == StatusCode.ERROR
    assert status.description == "something failed"


def test_set_span_error() -> None:
    """Mark a span as failed."""
    span = MagicMock()

    tracing.set_span_error(
        span,
        "operation failed",
    )

    status = span.set_status.call_args.args[0]

    assert status.status_code == StatusCode.ERROR
    assert status.description == "operation failed"


def test_add_span_event() -> None:
    """Add an event without attributes."""
    span = MagicMock()

    tracing.add_span_event(
        span,
        "plan.created",
    )

    span.add_event.assert_called_once_with(
        "plan.created",
        attributes=None,
    )


def test_add_span_event_with_attributes() -> None:
    """Add an event with normalized attributes."""
    span = MagicMock()

    tracing.add_span_event(
        span,
        "plan.created",
        attributes={
            "step_count": 2,
            "intent": "legal_research",
            "ignored": None,
        },
    )

    span.add_event.assert_called_once_with(
        "plan.created",
        attributes={
            "step_count": 2,
            "intent": "legal_research",
        },
    )
