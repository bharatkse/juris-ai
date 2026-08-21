"""
Approval-related data transfer objects.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.core.enums import ApprovalDecisionEnum, ApprovalStatusEnum


@dataclass(frozen=True, slots=True)
class ApprovalPolicyResultDTO:
    """
    Result of evaluating whether an action requires
    human approval.
    """

    decision: ApprovalDecisionEnum

    reason: str

    @property
    def requires_approval(self) -> bool:
        return self.decision == ApprovalDecisionEnum.REQUIRE_APPROVAL


@dataclass(frozen=True, slots=True)
class ApprovalRequestDTO:
    """
    Represents the data required to create a human
    approval request.

    The approval ID and creation timestamp are generated
    by persistence.
    """

    action_id: str

    action_fingerprint: str

    requested_by: str

    status: ApprovalStatusEnum

    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ApprovalResponseDTO:
    """
    Represents a persisted human approval request.

    Approval is bound to a specific persisted action.
    """

    approval_id: str

    action_id: str

    action_fingerprint: str

    requested_by: str

    status: ApprovalStatusEnum

    created_at: datetime

    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        return (
            datetime.now(
                self.expires_at.tzinfo,
            )
            >= self.expires_at
        )

    @property
    def is_waiting(self) -> bool:
        return self.status == ApprovalStatusEnum.WAITING

    @property
    def is_approved(self) -> bool:
        return self.status == ApprovalStatusEnum.APPROVED
