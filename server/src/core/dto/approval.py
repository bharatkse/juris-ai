"""
Approval-related data transfer objects.

Approval represents a human decision required before
a concrete AgentAction can continue to execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.enums import (
    ApprovalDecisionEnum,
    ApprovalPolicyDecisionEnum,
    ApprovalStatusEnum,
)


@dataclass(frozen=True, slots=True)
class ApprovalPolicyResultDTO:
    """
    Result of evaluating whether an action requires
    human approval.

    This is a policy decision only. It is not a persisted
    approval request.
    """

    decision: ApprovalPolicyDecisionEnum
    reason: str

    @property
    def requires_approval(self) -> bool:
        """
        Return whether human approval is required.
        """

        return self.decision == ApprovalPolicyDecisionEnum.REQUIRE_APPROVAL

    @property
    def allowed_without_approval(self) -> bool:
        """
        Return whether the action can continue without HITL.
        """

        return self.decision == ApprovalPolicyDecisionEnum.ALLOW


@dataclass(frozen=True, slots=True)
class ApprovalRequestDTO:
    """
    Data required to create a human approval request.

    The approval ID and creation timestamp are generated
    by persistence.
    """

    agent_action_id: str
    requested_by: str
    expires_at: datetime

    status: ApprovalStatusEnum = ApprovalStatusEnum.WAITING


@dataclass(frozen=True, slots=True)
class ApprovalDecisionRequestDTO:
    """
    Represents a human decision submitted for an approval.

    EDIT may optionally provide a modified action payload.
    """

    decision: ApprovalDecisionEnum

    edited_payload: dict[str, Any] | None = None

    decision_reason: str | None = None

    @property
    def is_approve(self) -> bool:
        """
        Return whether the decision is APPROVE.
        """

        return self.decision == ApprovalDecisionEnum.APPROVE

    @property
    def is_reject(self) -> bool:
        """
        Return whether the decision is REJECT.
        """

        return self.decision == ApprovalDecisionEnum.REJECT

    @property
    def is_edit(self) -> bool:
        """
        Return whether the decision is EDIT.
        """

        return self.decision == ApprovalDecisionEnum.EDIT


@dataclass(frozen=True, slots=True)
class ApprovalResponseDTO:
    """
    Represents a persisted human approval request.

    An approval is bound to exactly one AgentAction.
    """

    approval_id: str

    agent_action_id: str

    requested_by: str

    approved_by: str | None

    status: ApprovalStatusEnum

    decision_type: ApprovalDecisionEnum | None

    decision_reason: str | None

    edited_payload: dict[str, Any] | None

    edited_fingerprint: str | None

    expires_at: datetime

    created_at: datetime

    decided_at: datetime | None

    @property
    def is_expired(self) -> bool:
        """
        Return whether the approval has expired.
        """

        return (
            datetime.now(
                self.expires_at.tzinfo,
            )
            >= self.expires_at
        )

    @property
    def is_waiting(self) -> bool:
        """
        Return whether the approval is waiting for a decision.
        """

        return self.status == ApprovalStatusEnum.WAITING

    @property
    def is_approved(self) -> bool:
        """
        Return whether the approval is approved.
        """

        return self.status == ApprovalStatusEnum.APPROVED

    @property
    def is_rejected(self) -> bool:
        """
        Return whether the approval is rejected.
        """

        return self.status == ApprovalStatusEnum.REJECTED

    @property
    def is_edited(self) -> bool:
        """
        Return whether the approval was edited.
        """

        return self.status == ApprovalStatusEnum.EDITED

    @property
    def is_decided(self) -> bool:
        """
        Return whether a human decision has been made.
        """

        return self.status in {
            ApprovalStatusEnum.APPROVED,
            ApprovalStatusEnum.REJECTED,
            ApprovalStatusEnum.EDITED,
        }

    @property
    def is_active(self) -> bool:
        """
        Return whether the approval is still actionable.
        """

        return self.status == ApprovalStatusEnum.WAITING and not self.is_expired
