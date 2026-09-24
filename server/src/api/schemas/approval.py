"""
Approval API schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.enums import ApprovalDecisionEnum, ApprovalStatusEnum, HitlResumeStatusEnum


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

    Field names mirror ApprovalResponseDTO (core/dto/approval.py)
    exactly -- ApprovalLifecycleService.process() returns that DTO
    (via the persisted Approval entity's to_dto()), and this schema is
    built from it with from_attributes=True, so a name here that
    doesn't exist on the DTO fails validation on every call. Previously
    named `action_id`/`action_fingerprint`, neither a real attribute on
    the DTO (it has `agent_action_id`, no fingerprint field at all --
    that lives on AgentAction, not Approval) -- this endpoint 500'd on
    every decision, after the decision itself was already durably
    recorded. Found while building the HITL approve-flow E2E test
    (tests/e2e/test_hitl_approval_flow.py), which exercises this
    response shape for real.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    approval_id: str

    agent_action_id: str

    requested_by: str

    status: ApprovalStatusEnum

    created_at: datetime

    expires_at: datetime

    # Not on ApprovalResponseDTO: the endpoint sets it from
    # HitlResumeService's result after the decision is committed.
    resume_status: HitlResumeStatusEnum | None = None
