"""
Unit tests for streaming utilities.
"""

from __future__ import annotations

import json

from pydantic import BaseModel

from api.utilities.streaming import encode_sse_event


class DummyEvent(BaseModel):
    """
    Dummy event used for testing.
    """

    message: str
    count: int


def test_encode_sse_event_returns_valid_sse_message() -> None:
    """
    It should encode a model as a Server-Sent Event.
    """

    event = DummyEvent(
        message="Hello",
        count=1,
    )

    encoded = encode_sse_event(
        event,
    )

    expected = (
        "data: "
        + json.dumps(
            event.model_dump(
                mode="json",
            ),
            separators=(",", ":"),
        )
        + "\n\n"
    )

    assert encoded == expected


def test_encode_sse_event_serializes_json_payload() -> None:
    """
    It should serialize the model using JSON mode.
    """

    event = DummyEvent(
        message="Legal AI",
        count=10,
    )

    encoded = encode_sse_event(
        event,
    )

    payload = encoded.removeprefix(
        "data: ",
    ).removesuffix(
        "\n\n",
    )

    assert json.loads(
        payload,
    ) == {
        "message": "Legal AI",
        "count": 10,
    }


def test_encode_sse_event_uses_sse_format() -> None:
    """
    It should produce a valid SSE event.
    """

    event = DummyEvent(
        message="Hello",
        count=5,
    )

    encoded = encode_sse_event(
        event,
    )

    assert encoded.startswith(
        "data: ",
    )

    assert encoded.endswith(
        "\n\n",
    )


def test_encode_sse_event_includes_event_name() -> None:
    """
    It should include the SSE event name when provided.
    """

    event = DummyEvent(
        message="Hello",
        count=1,
    )

    encoded = encode_sse_event(
        event,
        event_name="message",
    )

    assert encoded == ("event: message\n" 'data: {"message":"Hello","count":1}\n\n')


def test_encode_sse_event_includes_event_id() -> None:
    """
    It should include the SSE event ID when provided.
    """

    event = DummyEvent(
        message="Hello",
        count=1,
    )

    encoded = encode_sse_event(
        event,
        event_id="event-123",
    )

    assert encoded == ("id: event-123\n" 'data: {"message":"Hello","count":1}\n\n')


def test_encode_sse_event_includes_retry() -> None:
    """
    It should include the retry interval when provided.
    """

    event = DummyEvent(
        message="Hello",
        count=1,
    )

    encoded = encode_sse_event(
        event,
        retry=5000,
    )

    assert encoded == ("retry: 5000\n" 'data: {"message":"Hello","count":1}\n\n')


def test_encode_sse_event_includes_all_sse_fields() -> None:
    """
    It should include event name, ID, retry, and data.
    """

    event = DummyEvent(
        message="Hello",
        count=1,
    )

    encoded = encode_sse_event(
        event,
        event_name="complete",
        event_id="event-123",
        retry=5000,
    )

    assert encoded == (
        "event: complete\n"
        "id: event-123\n"
        "retry: 5000\n"
        'data: {"message":"Hello","count":1}\n\n'
    )
