from datetime import UTC, datetime, timedelta

import pytest

from src.authorization.approval_lifecycle.service import ApprovalLifecycleService
from src.core.dto.agent_action import AgentActionRequestDTO
from src.core.enums import ActionTypeEnum, ApprovalStatusEnum
from src.core.exceptions.authorization import AuthorizationError


def create_action() -> AgentActionRequestDTO:
    return AgentActionRequestDTO(
        tool_name="email",
        action=ActionTypeEnum.SEND,
        arguments={
            "to": "client@example.com",
            "subject": "Contract",
        },
        reason="Send approved contract.",
    )


def test_create_creates_waiting_approval() -> None:
    service = ApprovalLifecycleService(
        approval_ttl_seconds=900,
    )

    approval = service.create(
        execution_id="execution-1",
        action_id="action-1",
        action=create_action(),
        requested_by="user-1",
    )

    assert approval.status == ApprovalStatusEnum.WAITING
    assert approval.execution_id == "execution-1"
    assert approval.action_id == "action-1"
    assert approval.requested_by == "user-1"
    assert approval.approval_id
    assert approval.action_fingerprint
    assert approval.expires_at > approval.created_at


def test_approve_changes_status_to_approved() -> None:
    service = ApprovalLifecycleService()

    approval = service.create(
        execution_id="execution-1",
        action_id="action-1",
        action=create_action(),
        requested_by="user-1",
    )

    result = service.approve(
        approval.approval_id,
    )

    assert result.status == ApprovalStatusEnum.APPROVED


def test_reject_changes_status_to_rejected() -> None:
    service = ApprovalLifecycleService()

    approval = service.create(
        execution_id="execution-1",
        action_id="action-1",
        action=create_action(),
        requested_by="user-1",
    )

    result = service.reject(
        approval.approval_id,
    )

    assert result.status == ApprovalStatusEnum.REJECTED


def test_edit_invalidates_approval() -> None:
    service = ApprovalLifecycleService()

    approval = service.create(
        execution_id="execution-1",
        action_id="action-1",
        action=create_action(),
        requested_by="user-1",
    )

    result = service.edit(
        approval.approval_id,
    )

    assert result.status == ApprovalStatusEnum.EDITED


def test_expired_approval_cannot_be_approved() -> None:
    service = ApprovalLifecycleService(
        approval_ttl_seconds=1,
    )

    approval = service.create(
        execution_id="execution-1",
        action_id="action-1",
        action=create_action(),
        requested_by="user-1",
    )

    # Make the stored approval expired.
    expired = approval.__class__(
        approval_id=approval.approval_id,
        execution_id=approval.execution_id,
        action_id=approval.action_id,
        action_fingerprint=approval.action_fingerprint,
        requested_by=approval.requested_by,
        status=ApprovalStatusEnum.WAITING,
        created_at=datetime.now(UTC) - timedelta(minutes=10),
        expires_at=datetime.now(UTC) - timedelta(minutes=5),
    )

    service._approvals[approval.approval_id] = expired

    with pytest.raises(
        AuthorizationError,
        match="not actionable",
    ):
        service.approve(
            approval.approval_id,
        )

    stored = service.get.__self__._approvals[approval.approval_id]

    assert stored.status == ApprovalStatusEnum.EXPIRED
