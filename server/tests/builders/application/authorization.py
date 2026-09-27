"""
Unit tests for execute-time RBAC authorization gate.
"""

from __future__ import annotations

from core.dto.authorization import AuthorizationRequestDTO
from core.enums import ActionTypeEnum


def build_authorization_request(
    **kwargs,
) -> AuthorizationRequestDTO:
    """
    Build an authorization request for tests.
    """

    data = {
        "user_id": "user_" + "a" * 32,
        "agent_id": "agent_" + "b" * 32,
        "tool_name": "send_email",
        "action_type": ActionTypeEnum.SEND,
        "resource_id": "resource_" + "c" * 32,
    }

    data.update(kwargs)

    return AuthorizationRequestDTO(
        **data,
    )
