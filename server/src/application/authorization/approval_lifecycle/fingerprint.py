"""
Action fingerprint generation.
"""

from __future__ import annotations

import hashlib
import json

from core.dto.agent_action import AgentActionResponseDTO


def create_action_fingerprint(
    action: AgentActionResponseDTO,
) -> str:
    """
    Create a deterministic fingerprint for the exact action version.

    The fingerprint covers the fields that define the executable
    action payload and target.
    """

    payload = {
        "agent_id": action.agent_id,
        "action_type": action.action_type.value,
        "tool_name": action.tool_name,
        "target_agent_id": action.target_agent_id,
        "resource_type": action.resource_type,
        "resource_id": action.resource_id,
        "parameters": action.parameters,
        "reason": action.reason,
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(
        serialized,
    ).hexdigest()
