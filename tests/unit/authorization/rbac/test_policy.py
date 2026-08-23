"""
Unit tests for RBACPolicy.
"""

from __future__ import annotations

import pytest

from src.authorization.rbac.policy import RBACPolicy
from src.core.enums import ActionTypeEnum


class TestRBACPolicyDefault:
    """Tests for the default RBAC policy."""

    def test_default_policy_returns_rbac_policy(self) -> None:
        """Default policy should return an RBACPolicy instance."""
        policy = RBACPolicy.default()

        assert isinstance(policy, RBACPolicy)

    def test_default_policy_is_frozen(self) -> None:
        """RBACPolicy should be immutable because it is frozen."""
        policy = RBACPolicy.default()

        with pytest.raises(AttributeError):
            policy.capability_permissions = {}

    def test_default_policy_contains_expected_capability_permissions(
        self,
        policy: RBACPolicy,
    ) -> None:
        """Default policy should contain expected user capabilities."""
        assert policy.capability_permissions == {
            "user-1": {
                ActionTypeEnum.READ,
                ActionTypeEnum.ANALYZE,
            },
        }

    def test_default_policy_contains_expected_user_actions(
        self,
        policy: RBACPolicy,
    ) -> None:
        """Default policy should contain expected user actions."""
        assert policy.user_action_permissions == {
            "user-1": {
                ActionTypeEnum.READ,
                ActionTypeEnum.ANALYZE,
                ActionTypeEnum.GENERATE,
            },
        }

    def test_default_policy_contains_expected_agent_actions(
        self,
        policy: RBACPolicy,
    ) -> None:
        """Default policy should contain expected agent/tool permissions."""
        assert policy.agent_action_permissions == {
            "legal": {
                "retriever": {
                    ActionTypeEnum.READ,
                    ActionTypeEnum.ANALYZE,
                },
            },
            "contract": {
                "retriever": {
                    ActionTypeEnum.READ,
                    ActionTypeEnum.ANALYZE,
                },
            },
        }


class TestCapabilityAllowed:
    """Tests for capability_allowed."""

    @pytest.mark.parametrize(
        ("user_id", "capability"),
        [
            ("user-1", ActionTypeEnum.READ),
            ("user-1", ActionTypeEnum.ANALYZE),
        ],
    )
    def test_allowed_capability(
        self,
        policy: RBACPolicy,
        user_id: str,
        capability: ActionTypeEnum,
    ) -> None:
        """Configured capabilities should be allowed."""
        assert (
            policy.capability_allowed(
                user_id=user_id,
                capability=capability,
            )
            is True
        )

    def test_denied_capability(
        self,
        policy: RBACPolicy,
    ) -> None:
        """A capability not granted to the user should be denied."""
        assert (
            policy.capability_allowed(
                user_id="user-1",
                capability=ActionTypeEnum.GENERATE,
            )
            is False
        )

    def test_unknown_user_is_denied(
        self,
        policy: RBACPolicy,
    ) -> None:
        """Unknown users should have no capabilities."""
        assert (
            policy.capability_allowed(
                user_id="unknown-user",
                capability=ActionTypeEnum.READ,
            )
            is False
        )

    def test_empty_user_id_is_denied(
        self,
        policy: RBACPolicy,
    ) -> None:
        """An empty user ID should not have capabilities."""
        assert (
            policy.capability_allowed(
                user_id="",
                capability=ActionTypeEnum.READ,
            )
            is False
        )


class TestUserActionAllowed:
    """Tests for user_action_allowed."""

    @pytest.mark.parametrize(
        "action",
        [
            ActionTypeEnum.READ,
            ActionTypeEnum.ANALYZE,
            ActionTypeEnum.GENERATE,
        ],
    )
    def test_allowed_user_action(
        self,
        policy: RBACPolicy,
        action: ActionTypeEnum,
    ) -> None:
        """Configured user actions should be allowed."""
        assert (
            policy.user_action_allowed(
                user_id="user-1",
                action=action,
            )
            is True
        )

    def test_denied_user_action(
        self,
        policy: RBACPolicy,
    ) -> None:
        """An action not granted to the user should be denied."""
        # Replace this with another ActionTypeEnum member if the enum
        # contains additional actions.
        denied_action = next(
            action
            for action in ActionTypeEnum
            if action
            not in {
                ActionTypeEnum.READ,
                ActionTypeEnum.ANALYZE,
                ActionTypeEnum.GENERATE,
            }
        )

        assert (
            policy.user_action_allowed(
                user_id="user-1",
                action=denied_action,
            )
            is False
        )

    def test_unknown_user_is_denied(
        self,
        policy: RBACPolicy,
    ) -> None:
        """Unknown users should have no actions."""
        assert (
            policy.user_action_allowed(
                user_id="unknown-user",
                action=ActionTypeEnum.READ,
            )
            is False
        )

    def test_empty_user_id_is_denied(
        self,
        policy: RBACPolicy,
    ) -> None:
        """An empty user ID should not have actions."""
        assert (
            policy.user_action_allowed(
                user_id="",
                action=ActionTypeEnum.READ,
            )
            is False
        )


class TestAgentActionAllowed:
    """Tests for agent_action_allowed."""

    @pytest.mark.parametrize(
        ("agent_id", "tool_name", "action"),
        [
            ("legal", "retriever", ActionTypeEnum.READ),
            ("legal", "retriever", ActionTypeEnum.ANALYZE),
            ("contract", "retriever", ActionTypeEnum.READ),
            ("contract", "retriever", ActionTypeEnum.ANALYZE),
        ],
    )
    def test_allowed_agent_action(
        self,
        policy: RBACPolicy,
        agent_id: str,
        tool_name: str,
        action: ActionTypeEnum,
    ) -> None:
        """Configured agent/tool actions should be allowed."""
        assert (
            policy.agent_action_allowed(
                agent_id=agent_id,
                tool_name=tool_name,
                action=action,
            )
            is True
        )

    def test_denied_agent_action(
        self,
        policy: RBACPolicy,
    ) -> None:
        """An action not granted to an agent/tool should be denied."""
        assert (
            policy.agent_action_allowed(
                agent_id="legal",
                tool_name="retriever",
                action=ActionTypeEnum.GENERATE,
            )
            is False
        )

    def test_unknown_agent_is_denied(
        self,
        policy: RBACPolicy,
    ) -> None:
        """Unknown agents should have no permissions."""
        assert (
            policy.agent_action_allowed(
                agent_id="unknown-agent",
                tool_name="retriever",
                action=ActionTypeEnum.READ,
            )
            is False
        )

    def test_unknown_tool_is_denied(
        self,
        policy: RBACPolicy,
    ) -> None:
        """Unknown tools should have no permissions."""
        assert (
            policy.agent_action_allowed(
                agent_id="legal",
                tool_name="unknown-tool",
                action=ActionTypeEnum.READ,
            )
            is False
        )

    @pytest.mark.parametrize(
        "tool_name",
        [
            None,
            "",
        ],
    )
    def test_missing_tool_name_is_denied(
        self,
        policy: RBACPolicy,
        tool_name: str | None,
    ) -> None:
        """A concrete agent action requires a tool name."""
        assert (
            policy.agent_action_allowed(
                agent_id="legal",
                tool_name=tool_name,
                action=ActionTypeEnum.READ,
            )
            is False
        )

    def test_agent_cannot_use_another_agents_tool_permission(
        self,
        policy: RBACPolicy,
    ) -> None:
        """Permissions should remain scoped to the configured agent."""
        assert (
            policy.agent_action_allowed(
                agent_id="unknown-agent",
                tool_name="retriever",
                action=ActionTypeEnum.READ,
            )
            is False
        )
