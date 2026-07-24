"""
Streaming utilities.
"""

from __future__ import annotations

import json

from pydantic import BaseModel


def encode_sse_event(
    event: BaseModel,
) -> str:
    """
    Encode a Server-Sent Event.
    """

    return f"data: {json.dumps(event.model_dump(mode='json'))}\n\n"
