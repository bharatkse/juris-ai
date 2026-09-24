"""
Human approval policy.
"""

from __future__ import annotations

from core.dto.agent_action import AgentActionResponseDTO
from core.dto.approval import ApprovalPolicyResultDTO
from core.enums import ActionTypeEnum, ApprovalPolicyDecisionEnum


class ApprovalLifecyclePolicy:
    """
    Determines whether a concrete action requires human approval.

    Approval policy is independent of:
    - capability analysis,
    - RBAC authorization,
    - approval persistence,
    - action execution.
    """

    _APPROVAL_REQUIRED_ACTIONS: frozenset[ActionTypeEnum] = frozenset(
        {
            ActionTypeEnum.SEND,
        },
    )

    def evaluate(
        self,
        action: AgentActionResponseDTO,
    ) -> ApprovalPolicyResultDTO:
        """
        Determine whether the concrete action requires
        human approval.
        """

        if action.action_type in self._APPROVAL_REQUIRED_ACTIONS:
            return ApprovalPolicyResultDTO(
                decision=ApprovalPolicyDecisionEnum.REQUIRE_APPROVAL,
                reason=(f"Action '{action.action_type.value}' " "requires human approval."),
            )

        return ApprovalPolicyResultDTO(
            decision=ApprovalPolicyDecisionEnum.ALLOW,
            reason=(f"Action '{action.action_type.value}' " "does not require human approval."),
        )
