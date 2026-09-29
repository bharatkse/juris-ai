"""
Unit tests for RBACPolicy: agent -> tool -> action permissions.

User permissions are not in RBACPolicy any more: they come from the
user's role in the database (see test_roles.py and
tests/e2e/test_user_roles.py).
"""

from __future__ import annotations

import pytest

from application.authorization.rbac.policy import RBACPolicy
from core.enums import ActionTypeEnum


def test_default_policy_is_frozen() -> None:
    policy = RBACPolicy.default()

    with pytest.raises(AttributeError):
        policy.agent_action_permissions = {}  # type: ignore[misc]


class TestAgentActionAllowed:
    """Tests for agent_action_allowed."""

    @pytest.mark.parametrize(
        ("agent_id", "tool_name", "action"),
        [
            ("legal", "retriever", ActionTypeEnum.READ),
            ("legal", "retriever", ActionTypeEnum.ANALYZE),
            ("contract", "retriever", ActionTypeEnum.READ),
            ("contract", "retriever", ActionTypeEnum.ANALYZE),
            ("legal", "email_send", ActionTypeEnum.SEND),
            ("legal", "slack_post", ActionTypeEnum.SEND),
            ("contract", "email_send", ActionTypeEnum.SEND),
            ("contract", "slack_post", ActionTypeEnum.SEND),
        ],
    )
    def test_allowed_agent_action(
        self,
        policy: RBACPolicy,
        agent_id: str,
        tool_name: str,
        action: ActionTypeEnum,
    ) -> None:
        assert (
            policy.agent_action_allowed(agent_id=agent_id, tool_name=tool_name, action=action)
            is True
        )

    @pytest.mark.parametrize(
        ("tool_name", "action"),
        [
            ("retriever", ActionTypeEnum.GENERATE),
            ("retriever", ActionTypeEnum.SEND),
            # The read tools never become SEND actions.
            ("email", ActionTypeEnum.SEND),
            ("slack", ActionTypeEnum.SEND),
            ("email_send", ActionTypeEnum.READ),
            ("unknown-tool", ActionTypeEnum.READ),
        ],
    )
    def test_denied_agent_action(
        self,
        policy: RBACPolicy,
        tool_name: str,
        action: ActionTypeEnum,
    ) -> None:
        assert (
            policy.agent_action_allowed(agent_id="legal", tool_name=tool_name, action=action)
            is False
        )

    def test_unknown_agent_is_denied(self, policy: RBACPolicy) -> None:
        assert (
            policy.agent_action_allowed(
                agent_id="unknown-agent",
                tool_name="email_send",
                action=ActionTypeEnum.SEND,
            )
            is False
        )

    @pytest.mark.parametrize("tool_name", [None, ""])
    def test_missing_tool_name_is_denied(
        self,
        policy: RBACPolicy,
        tool_name: str | None,
    ) -> None:
        assert (
            policy.agent_action_allowed(
                agent_id="legal",
                tool_name=tool_name,
                action=ActionTypeEnum.READ,
            )
            is False
        )
