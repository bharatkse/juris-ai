"""
Approval API schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.core.enums import ApprovalDecisionEnum, ApprovalStatusEnum


class ApprovalDecisionRequest(BaseModel):
    """
    Request to apply a decision to an approval request.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    decision: ApprovalDecisionEnum = Field(
        description="Decision to apply to the approval request.",
    )

    edited_payload: dict[str, Any] | None = None

    decision_reason: str | None = None


class ApprovalResponse(BaseModel):
    """
    Approval request returned by the API.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    approval_id: str

    action_id: str

    action_fingerprint: str

    requested_by: str

    status: ApprovalStatusEnum

    created_at: datetime

    expires_at: datetime
