"""
RBAC permission policy.

Agent action permissions only. What a user may do comes from their role
in the database (rbac/roles.py).
"""

from __future__ import annotations

from dataclasses import dataclass

from core.enums import ActionTypeEnum


@dataclass(frozen=True, slots=True)
class RBACPolicy:
    """
    Agent action permissions: agent -> tool -> action.

    User permissions are not here: they come from the user's role in the
    database (rbac/roles.py, DatabaseRolePermissionProvider).
    """

    agent_action_permissions: dict[
        str,
        dict[
            str,
            frozenset[ActionTypeEnum],
        ],
    ]

    @classmethod
    def default(cls) -> RBACPolicy:
        """
        Create the application's agent action policy.
        """

        # Only gated sends become concrete business actions checked
        # against agent permissions (ActionWorkflowService); ordinary
        # tool calls are governed by the agent_policies table
        # (agentic/policy/). Which agent may call a send tool at all is
        # decided there too (ENABLE_MESSAGING_TOOLS).
        agent_tools: dict[str, frozenset[ActionTypeEnum]] = {
            "retriever": frozenset({ActionTypeEnum.READ, ActionTypeEnum.ANALYZE}),
            "email_send": frozenset({ActionTypeEnum.SEND}),
            "slack_post": frozenset({ActionTypeEnum.SEND}),
        }

        return cls(
            agent_action_permissions={
                "legal": dict(agent_tools),
                "contract": dict(agent_tools),
            },
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
            frozenset(),
        )
