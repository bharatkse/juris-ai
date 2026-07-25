"""
Unit tests for RequestContext.
"""

from __future__ import annotations

from src.core.context import RequestContext
from src.schemas.base import AIInfoModel


def test_request_context_generates_request_id() -> None:
    """
    It should generate a request identifier by default.
    """

    context = RequestContext()

    assert context.request_id
    assert isinstance(
        context.request_id,
        str,
    )


def test_request_context_uses_provided_values() -> None:
    """
    It should store the provided context values.
    """

    ai = AIInfoModel(
        provider="groq",
        model="llama-3",
    )

    context = RequestContext(
        request_id="request_123",
        conversation_id="conversation_123",
        trace_id="trace_123",
        ai=ai,
    )

    assert context.request_id == "request_123"
    assert context.conversation_id == "conversation_123"
    assert context.trace_id == "trace_123"
    assert context.ai is ai


def test_to_metadata_returns_metadata() -> None:
    """
    It should convert the request context into metadata.
    """

    ai = AIInfoModel(
        provider="groq",
        model="llama-3",
    )

    context = RequestContext(
        request_id="request_123",
        conversation_id="conversation_123",
        trace_id="trace_123",
        ai=ai,
    )

    metadata = context.to_metadata()

    assert metadata.request_id == "request_123"
    assert metadata.conversation_id == "conversation_123"
    assert metadata.trace_id == "trace_123"
    assert metadata.ai is ai


def test_to_metadata_uses_defaults() -> None:
    """
    It should create metadata when optional values are absent.
    """

    context = RequestContext()

    metadata = context.to_metadata()

    assert metadata.request_id == context.request_id
    assert metadata.conversation_id is None
    assert metadata.trace_id is None
    assert metadata.ai is None
    assert metadata.timestamp is not None
