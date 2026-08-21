"""
Action fingerprint generation.
"""

from __future__ import annotations

import hashlib
import json

from src.core.dto.action import ActionRequestDTO


def create_action_fingerprint(
    action: ActionRequestDTO,
) -> str:
    """
    Create a deterministic fingerprint for an exact action version.
    """

    payload = {
        "tool_name": action.tool_name,
        "action": action.action.value,
        "agent_id": action.agent_id,
        "arguments": action.arguments,
        "reason": action.reason,
        "resource_id": action.resource_id,
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(serialized).hexdigest()
