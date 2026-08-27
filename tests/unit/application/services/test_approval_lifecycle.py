"""
Unit tests for approval lifecycle application service.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adapters.persistence.sqlalchemy.models.approval import Approval
from adapters.persistence.sqlalchemy.repositories.approval import ApprovalRepository
from application.services.approval_lifecycle import ApprovalLifecycleService
from core.dto.agent_action import AgentActionResponseDTO
from core.dto.approval import ApprovalDecisionRequestDTO
from core.enums import ApprovalDecisionEnum, ApprovalStatusEnum
from core.exceptions.approval import (
    ApprovalError,
    ApprovalExpiredError,
    ApprovalNotActionableError,
    ApprovalNotFoundError,
    ApprovalValidationError,
)


def build_action() -> MagicMock:
    """
    Build a mocked AgentActionResponseDTO.
    """

    action = MagicMock(
        spec=AgentActionResponseDTO,
    )

    action.action_id = "action-123"

    return action


def build_approval_entity(
    *,
    status: ApprovalStatusEnum = ApprovalStatusEnum.WAITING,
    expired: bool = False,
) -> MagicMock:
    """
    Build a mocked Approval entity.
    """

    entity = MagicMock(
        spec=Approval,
    )

    entity.id = "approval-123"
    entity.agent_action_id = "action-123"
    entity.status = status
    entity.is_expired = expired
    entity.approved_by = None
    entity.decision_type = None
    entity.decision_reason = None
    entity.edited_payload = None
    entity.decided_at = None

    return entity


@pytest.fixture
def repository() -> MagicMock:
    """
    Provide a mocked approval repository.
    """

    repository = MagicMock(
        spec=ApprovalRepository,
    )

    repository.create = AsyncMock()
    repository.get = AsyncMock()
    repository.save = AsyncMock()

    return repository


@pytest.fixture
def session() -> MagicMock:
    """
    Provide a mocked database session.
    """

    return MagicMock()


@pytest.fixture
def service(
    session: MagicMock,
    repository: MagicMock,
) -> ApprovalLifecycleService:
    """
    Create an ApprovalLifecycleService with mocked dependencies.
    """

    return ApprovalLifecycleService(
        session=session,
        repository=repository,
    )


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


def test_init_rejects_non_positive_ttl(
    session: MagicMock,
    repository: MagicMock,
) -> None:
    """
    It should reject a non-positive approval TTL.
    """

    with pytest.raises(
        ValueError,
        match="Approval TTL must be greater than zero.",
    ):
        ApprovalLifecycleService(
            session=session,
            repository=repository,
            approval_ttl_seconds=0,
        )


@pytest.mark.parametrize(
    "ttl",
    [-1, -100],
)
def test_init_rejects_negative_ttl(
    session: MagicMock,
    repository: MagicMock,
    ttl: int,
) -> None:
    """
    It should reject negative approval TTL values.
    """

    with pytest.raises(
        ValueError,
        match="Approval TTL must be greater than zero.",
    ):
        ApprovalLifecycleService(
            session=session,
            repository=repository,
            approval_ttl_seconds=ttl,
        )


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch(
    "application.services.approval_lifecycle.Approval.from_dto",
)
async def test_create_creates_and_persists_approval(
    mock_from_dto: MagicMock,
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should construct and persist a waiting approval.
    """

    action = build_action()
    entity = build_approval_entity()

    response = MagicMock()

    entity.to_dto.return_value = response
    repository.create.return_value = entity
    mock_from_dto.return_value = entity

    before = datetime.now(UTC)

    result = await service.create(
        action=action,
        requested_by="user-123",
    )

    after = datetime.now(UTC)

    assert result is response

    mock_from_dto.assert_called_once()

    request = mock_from_dto.call_args.kwargs["approval"]

    assert request.agent_action_id == action.action_id
    assert request.requested_by == "user-123"
    assert before + timedelta(seconds=900) <= request.expires_at <= (after + timedelta(seconds=900))

    repository.create.assert_awaited_once_with(
        entity=entity,
    )


@pytest.mark.asyncio
@patch(
    "application.services.approval_lifecycle.Approval.from_dto",
)
async def test_create_uses_configured_ttl(
    mock_from_dto: MagicMock,
    session: MagicMock,
    repository: MagicMock,
) -> None:
    """
    It should calculate expiration using the configured TTL.
    """

    service = ApprovalLifecycleService(
        session=session,
        repository=repository,
        approval_ttl_seconds=60,
    )

    action = build_action()
    entity = build_approval_entity()

    mock_from_dto.return_value = entity
    repository.create.return_value = entity

    before = datetime.now(UTC)

    await service.create(
        action=action,
        requested_by="user-123",
    )

    after = datetime.now(UTC)

    request = mock_from_dto.call_args.kwargs["approval"]

    assert before + timedelta(seconds=60) <= request.expires_at <= (after + timedelta(seconds=60))


@pytest.mark.asyncio
@patch(
    "application.services.approval_lifecycle.Approval.from_dto",
)
async def test_create_propagates_approval_error(
    mock_from_dto: MagicMock,
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should propagate ApprovalError unchanged.
    """

    action = build_action()

    error = ApprovalError(
        "approval creation failed",
    )

    mock_from_dto.side_effect = error

    with pytest.raises(
        ApprovalError,
        match="approval creation failed",
    ):
        await service.create(
            action=action,
            requested_by="user-123",
        )

    repository.create.assert_not_awaited()


@pytest.mark.asyncio
@patch(
    "application.services.approval_lifecycle.Approval.from_dto",
)
async def test_create_wraps_unexpected_error(
    mock_from_dto: MagicMock,
    service: ApprovalLifecycleService,
) -> None:
    """
    It should wrap unexpected creation errors.
    """

    action = build_action()

    error = RuntimeError(
        "database failure",
    )

    mock_from_dto.side_effect = error

    with pytest.raises(
        ApprovalError,
        match="Failed to create approval request.",
    ) as exc_info:
        await service.create(
            action=action,
            requested_by="user-123",
        )

    assert exc_info.value.__cause__ is error


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_approval_dto(
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should retrieve an approval and convert it to a DTO.
    """

    entity = build_approval_entity()
    response = MagicMock()

    entity.to_dto.return_value = response
    repository.get.return_value = entity

    result = await service.get(
        "approval-123",
    )

    assert result is response

    repository.get.assert_awaited_once_with(
        "approval-123",
    )

    entity.to_dto.assert_called_once_with()


@pytest.mark.asyncio
async def test_get_raises_not_found_when_repository_returns_none(
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should raise ApprovalNotFoundError when approval does not exist.
    """

    repository.get.return_value = None

    with pytest.raises(
        ApprovalNotFoundError,
        match="Approval request was not found.",
    ):
        await service.get(
            "missing-approval",
        )


@pytest.mark.asyncio
async def test_get_wraps_unexpected_repository_error(
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should wrap unexpected repository errors.
    """

    error = RuntimeError(
        "database unavailable",
    )

    repository.get.side_effect = error

    with pytest.raises(
        ApprovalError,
        match="Failed to retrieve approval request.",
    ) as exc_info:
        await service.get(
            "approval-123",
        )

    assert exc_info.value.__cause__ is error


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_returns_approved_approval(
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should return an approved, non-expired approval.
    """

    entity = build_approval_entity(
        status=ApprovalStatusEnum.APPROVED,
    )

    response = MagicMock()

    entity.to_dto.return_value = response
    repository.get.return_value = entity

    result = await service.validate(
        "approval-123",
    )

    assert result is response

    repository.get.assert_awaited_once_with(
        "approval-123",
    )

    entity.to_dto.assert_called_once_with()

    repository.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_raises_for_non_approved_status(
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should reject approvals that are not approved.
    """

    entity = build_approval_entity(
        status=ApprovalStatusEnum.WAITING,
    )

    repository.get.return_value = entity

    with pytest.raises(
        ApprovalValidationError,
        match="Approval is not valid for execution",
    ):
        await service.validate(
            "approval-123",
        )

    repository.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_expires_expired_approval(
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should persist an expired state before raising.
    """

    entity = build_approval_entity(
        status=ApprovalStatusEnum.APPROVED,
        expired=True,
    )

    repository.get.return_value = entity
    repository.save.return_value = entity

    with pytest.raises(
        ApprovalExpiredError,
        match="Approval has expired.",
    ):
        await service.validate(
            "approval-123",
        )

    assert entity.status is ApprovalStatusEnum.EXPIRED

    repository.save.assert_awaited_once_with(
        entity=entity,
    )


@pytest.mark.asyncio
async def test_validate_raises_not_found(
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should propagate ApprovalNotFoundError.
    """

    repository.get.return_value = None

    with pytest.raises(
        ApprovalNotFoundError,
    ):
        await service.validate(
            "approval-123",
        )


# ---------------------------------------------------------------------------
# process
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_routes_approve_decision(
    service: ApprovalLifecycleService,
) -> None:
    """
    It should route APPROVE decisions to approve().
    """

    expected = MagicMock()

    service.approve = AsyncMock(
        return_value=expected,
    )

    request = ApprovalDecisionRequestDTO(
        decision=ApprovalDecisionEnum.APPROVE,
        decision_reason="Looks good.",
    )

    result = await service.process(
        approval_id="approval-123",
        request=request,
        user_id="user-123",
    )

    assert result is expected

    service.approve.assert_awaited_once_with(
        approval_id="approval-123",
        user_id="user-123",
        decision_reason="Looks good.",
    )


@pytest.mark.asyncio
async def test_process_routes_reject_decision(
    service: ApprovalLifecycleService,
) -> None:
    """
    It should route REJECT decisions to reject().
    """

    expected = MagicMock()

    service.reject = AsyncMock(
        return_value=expected,
    )

    request = ApprovalDecisionRequestDTO(
        decision=ApprovalDecisionEnum.REJECT,
        decision_reason="Not permitted.",
    )

    result = await service.process(
        approval_id="approval-123",
        request=request,
        user_id="user-123",
    )

    assert result is expected

    service.reject.assert_awaited_once_with(
        approval_id="approval-123",
        user_id="user-123",
        decision_reason="Not permitted.",
    )


@pytest.mark.asyncio
async def test_process_routes_edit_decision(
    service: ApprovalLifecycleService,
) -> None:
    """
    It should route EDIT decisions to edit().
    """

    expected = MagicMock()

    service.edit = AsyncMock(
        return_value=expected,
    )

    payload = {
        "recipient": "new@example.com",
    }

    request = ApprovalDecisionRequestDTO(
        decision=ApprovalDecisionEnum.EDIT,
        edited_payload=payload,
        decision_reason="Change recipient.",
    )

    result = await service.process(
        approval_id="approval-123",
        request=request,
        user_id="user-123",
    )

    assert result is expected

    service.edit.assert_awaited_once_with(
        approval_id="approval-123",
        user_id="user-123",
        edited_payload=payload,
        decision_reason="Change recipient.",
    )


# ---------------------------------------------------------------------------
# approve
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_updates_waiting_approval(
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should approve a waiting approval.
    """

    entity = build_approval_entity()
    repository.get.return_value = entity
    repository.save.return_value = entity

    response = MagicMock()
    entity.to_dto.return_value = response

    before = datetime.now(UTC)

    result = await service.approve(
        approval_id="approval-123",
        user_id="approver-123",
        decision_reason="Approved by reviewer.",
    )

    after = datetime.now(UTC)

    assert result is response
    assert entity.status is ApprovalStatusEnum.APPROVED
    assert entity.approved_by == "approver-123"
    assert entity.decision_type is ApprovalDecisionEnum.APPROVE
    assert entity.decision_reason == "Approved by reviewer."
    assert before <= entity.decided_at <= after

    repository.save.assert_awaited_once_with(
        entity=entity,
    )


@pytest.mark.asyncio
async def test_approve_rejects_non_waiting_approval(
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should not approve an already processed approval.
    """

    entity = build_approval_entity(
        status=ApprovalStatusEnum.REJECTED,
    )

    repository.get.return_value = entity

    with pytest.raises(
        ApprovalNotActionableError,
        match="Approval is not actionable",
    ):
        await service.approve(
            approval_id="approval-123",
            user_id="approver-123",
        )

    repository.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_approve_rejects_expired_approval(
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should expire an expired waiting approval and reject approval.
    """

    entity = build_approval_entity(
        expired=True,
    )

    repository.get.return_value = entity
    repository.save.return_value = entity

    with pytest.raises(
        ApprovalExpiredError,
        match="Approval has expired.",
    ):
        await service.approve(
            approval_id="approval-123",
            user_id="approver-123",
        )

    assert entity.status is ApprovalStatusEnum.EXPIRED

    repository.save.assert_awaited_once_with(
        entity=entity,
    )


# ---------------------------------------------------------------------------
# reject
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reject_updates_waiting_approval(
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should reject a waiting approval.
    """

    entity = build_approval_entity()

    repository.get.return_value = entity
    repository.save.return_value = entity

    response = MagicMock()
    entity.to_dto.return_value = response

    before = datetime.now(UTC)

    result = await service.reject(
        approval_id="approval-123",
        user_id="reviewer-123",
        decision_reason="Action is not permitted.",
    )

    after = datetime.now(UTC)

    assert result is response
    assert entity.status is ApprovalStatusEnum.REJECTED
    assert entity.approved_by == "reviewer-123"
    assert entity.decision_type is ApprovalDecisionEnum.REJECT
    assert entity.decision_reason == "Action is not permitted."
    assert before <= entity.decided_at <= after

    repository.save.assert_awaited_once_with(
        entity=entity,
    )


@pytest.mark.asyncio
async def test_reject_propagates_not_actionable_error(
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should not reject an already processed approval.
    """

    entity = build_approval_entity(
        status=ApprovalStatusEnum.APPROVED,
    )

    repository.get.return_value = entity

    with pytest.raises(
        ApprovalNotActionableError,
    ):
        await service.reject(
            approval_id="approval-123",
            user_id="reviewer-123",
        )

    repository.save.assert_not_awaited()


# ---------------------------------------------------------------------------
# edit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_updates_waiting_approval(
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should mark a waiting approval as edited.
    """

    entity = build_approval_entity()

    repository.get.return_value = entity
    repository.save.return_value = entity

    response = MagicMock()
    entity.to_dto.return_value = response

    payload = {
        "recipient": "changed@example.com",
        "subject": "Updated subject",
    }

    before = datetime.now(UTC)

    result = await service.edit(
        approval_id="approval-123",
        user_id="reviewer-123",
        edited_payload=payload,
        decision_reason="Changed the request.",
    )

    after = datetime.now(UTC)

    assert result is response
    assert entity.status is ApprovalStatusEnum.EDITED
    assert entity.approved_by == "reviewer-123"
    assert entity.decision_type is ApprovalDecisionEnum.EDIT
    assert entity.decision_reason == "Changed the request."
    assert entity.edited_payload == payload
    assert before <= entity.decided_at <= after

    repository.save.assert_awaited_once_with(
        entity=entity,
    )


@pytest.mark.asyncio
async def test_edit_allows_none_payload(
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should allow an edit without an edited payload.
    """

    entity = build_approval_entity()

    repository.get.return_value = entity
    repository.save.return_value = entity

    await service.edit(
        approval_id="approval-123",
        user_id="reviewer-123",
        edited_payload=None,
    )

    assert entity.status is ApprovalStatusEnum.EDITED
    assert entity.edited_payload is None
    assert entity.decision_type is ApprovalDecisionEnum.EDIT


@pytest.mark.asyncio
async def test_edit_rejects_non_waiting_approval(
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should not edit an already processed approval.
    """

    entity = build_approval_entity(
        status=ApprovalStatusEnum.APPROVED,
    )

    repository.get.return_value = entity

    with pytest.raises(
        ApprovalNotActionableError,
    ):
        await service.edit(
            approval_id="approval-123",
            user_id="reviewer-123",
            edited_payload={
                "changed": True,
            },
        )

    repository.save.assert_not_awaited()


# ---------------------------------------------------------------------------
# persistence error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_wraps_unexpected_save_error(
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should wrap unexpected approval persistence errors.
    """

    entity = build_approval_entity()

    repository.get.return_value = entity

    error = RuntimeError(
        "database unavailable",
    )

    repository.save.side_effect = error

    with pytest.raises(
        ApprovalError,
        match="Failed to persist approval decision.",
    ) as exc_info:
        await service.approve(
            approval_id="approval-123",
            user_id="user-123",
        )

    assert exc_info.value.__cause__ is error


@pytest.mark.asyncio
async def test_reject_wraps_unexpected_save_error(
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should wrap unexpected rejection persistence errors.
    """

    entity = build_approval_entity()

    repository.get.return_value = entity

    error = RuntimeError(
        "database unavailable",
    )

    repository.save.side_effect = error

    with pytest.raises(
        ApprovalError,
        match="Failed to persist approval decision.",
    ) as exc_info:
        await service.reject(
            approval_id="approval-123",
            user_id="user-123",
        )

    assert exc_info.value.__cause__ is error


@pytest.mark.asyncio
async def test_edit_wraps_unexpected_save_error(
    service: ApprovalLifecycleService,
    repository: MagicMock,
) -> None:
    """
    It should wrap unexpected edit persistence errors.
    """

    entity = build_approval_entity()

    repository.get.return_value = entity

    error = RuntimeError(
        "database unavailable",
    )

    repository.save.side_effect = error

    with pytest.raises(
        ApprovalError,
        match="Failed to persist approval decision.",
    ) as exc_info:
        await service.edit(
            approval_id="approval-123",
            user_id="user-123",
            edited_payload={
                "changed": True,
            },
        )

    assert exc_info.value.__cause__ is error
