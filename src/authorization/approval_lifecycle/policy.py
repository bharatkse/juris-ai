"""
Human approval policy.
"""

from __future__ import annotations

from src.core.dto.action import ActionRequestDTO
from src.core.dto.approval import ApprovalPolicyResultDTO
from src.core.enums import ActionTypeEnum, ApprovalDecisionEnum


class ApprovalLifecyclePolicy:
    """
    Determines whether a concrete action requires human approval.

    Approval policy is independent of RBAC and capability analysis.
    """

    _APPROVAL_REQUIRED_ACTIONS: frozenset[ActionTypeEnum] = frozenset(
        {
            ActionTypeEnum.SEND,
        },
    )

    def evaluate(
        self,
        action: ActionRequestDTO,
    ) -> ApprovalPolicyResultDTO:
        """
        Determine whether the action requires human approval.
        """

        if action.action in self._APPROVAL_REQUIRED_ACTIONS:
            return ApprovalPolicyResultDTO(
                decision=ApprovalDecisionEnum.REQUIRE_APPROVAL,
                reason=(f"Action '{action.action}' requires " "human approval."),
            )

        return ApprovalPolicyResultDTO(
            decision=ApprovalDecisionEnum.ALLOW,
            reason=(f"Action '{action.action}' does not require " "human approval."),
        )
