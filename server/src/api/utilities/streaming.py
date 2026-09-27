"""
Streaming utilities.
"""

from __future__ import annotations

import json

from pydantic import BaseModel


def encode_sse_event(
    event: BaseModel,
    *,
    event_name: str | None = None,
    event_id: str | None = None,
    retry: int | None = None,
) -> str:
    """
    Encode a Server-Sent Event.
    """

    lines: list[str] = []

    if event_name is not None:
        lines.append(
            f"event: {event_name}",
        )

    if event_id is not None:
        lines.append(
            f"id: {event_id}",
        )

    if retry is not None:
        lines.append(
            f"retry: {retry}",
        )

    payload = json.dumps(
        event.model_dump(
            mode="json",
        ),
        separators=(",", ":"),
    )

    lines.append(
        f"data: {payload}",
    )

    return (
        "\n".join(
            lines,
        )
        + "\n\n"
    )
