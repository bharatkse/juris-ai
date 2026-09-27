"""
RBAC permission policy.

This module is the single source of truth for the current
RBAC permissions.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.enums import ActionTypeEnum


@dataclass(frozen=True, slots=True)
class RBACPolicy:
    """
    Defines RBAC permissions for users and agents.

    Capability permissions:
        user -> capability

    User action permissions:
        user -> action

    Agent action permissions:
        agent -> tool -> action
    """

    capability_permissions: dict[
        str,
        set[ActionTypeEnum],
    ]

    user_action_permissions: dict[
        str,
        set[ActionTypeEnum],
    ]

    agent_action_permissions: dict[
        str,
        dict[
            str,
            set[ActionTypeEnum],
        ],
    ]

    @classmethod
    def default(cls) -> RBACPolicy:
        """
        Create the default application RBAC policy.
        """

        return cls(
            capability_permissions={
                "user-1": {
                    ActionTypeEnum.READ,
                    ActionTypeEnum.ANALYZE,
                },
            },
            user_action_permissions={
                "user-1": {
                    ActionTypeEnum.READ,
                    ActionTypeEnum.ANALYZE,
                    ActionTypeEnum.GENERATE,
                },
            },
            agent_action_permissions={
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
            },
        )

    def capability_allowed(
        self,
        *,
        user_id: str,
        capability: ActionTypeEnum,
    ) -> bool:
        """
        Return whether a user may request a capability.
        """

        return capability in self.capability_permissions.get(
            user_id,
            set(),
        )

    def user_action_allowed(
        self,
        *,
        user_id: str,
        action: ActionTypeEnum,
    ) -> bool:
        """
        Return whether a user may perform an action.
        """

        return action in self.user_action_permissions.get(
            user_id,
            set(),
        )

    def agent_action_allowed(
        self,
        *,
        agent_id: str,
        tool_name: str | None,
        action: ActionTypeEnum,
    ) -> bool:
        """
        Return whether an agent may perform an action
        through the specified tool.

        A concrete tool action requires a tool name.
        """

        if not tool_name:
            return False

        agent_permissions = self.agent_action_permissions.get(
            agent_id,
            {},
        )

        return action in agent_permissions.get(
            tool_name,
            set(),
        )
