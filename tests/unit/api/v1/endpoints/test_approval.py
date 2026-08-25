"""
Unit tests for approval API routes.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.schemas.approval import ApprovalDecisionRequest
from src.api.v1.endpoints.approval import process_approval
from src.core.dto.approval import ApprovalDecisionRequestDTO
from src.core.enums import ApprovalDecisionEnum
from src.core.exceptions.authorization import AuthorizationError
from src.services.approval_lifecycle import ApprovalLifecycleService


def build_current_user() -> SimpleNamespace:
    """
    Build a minimal authenticated user for route tests.
    """

    return SimpleNamespace(
        id="user-123",
    )


def build_approval_result() -> SimpleNamespace:
    """
    Build a minimal approval entity for response serialization.
    """

    return SimpleNamespace(
        id="approval-123",
    )


@pytest.mark.asyncio
async def test_process_approval_returns_success_response() -> None:
    """
    It should process an approval and return a successful response.
    """

    service = MagicMock(
        spec=ApprovalLifecycleService,
    )
    service.process = AsyncMock(
        return_value=build_approval_result(),
    )

    current_user = build_current_user()

    request = ApprovalDecisionRequest(
        decision=ApprovalDecisionEnum.APPROVE,
        edited_payload=None,
        decision_reason="Approved by reviewer.",
    )

    with patch(
        "src.api.schemas.approval.ApprovalResponse.model_validate",
        return_value={"id": "approval-123"},
    ):
        result = await process_approval(
            approval_id="approval-123",
            request=request,
            current_user=current_user,
            service=service,
        )

    assert result.status_code == 200

    result = json.loads(result.body)

    assert result["success"] is True
    assert result["data"] == {"id": "approval-123"}

    service.process.assert_awaited_once()

    call = service.process.await_args

    assert call.kwargs["approval_id"] == "approval-123"
    assert call.kwargs["user_id"] == current_user.id

    decision_request = call.kwargs["request"]

    assert isinstance(
        decision_request,
        ApprovalDecisionRequestDTO,
    )

    assert decision_request.decision == request.decision
    assert decision_request.edited_payload == request.edited_payload
    assert decision_request.decision_reason == request.decision_reason


@pytest.mark.asyncio
async def test_process_approval_passes_edited_payload() -> None:
    """
    It should preserve an edited payload when processing approval.
    """

    service = MagicMock(
        spec=ApprovalLifecycleService,
    )
    service.process = AsyncMock(
        return_value=build_approval_result(),
    )

    current_user = build_current_user()

    edited_payload = {
        "recipient": "updated@example.com",
        "subject": "Updated subject",
    }

    request = ApprovalDecisionRequest(
        decision=ApprovalDecisionEnum.APPROVE,
        edited_payload=edited_payload,
        decision_reason="Updated before approval.",
    )

    with patch(
        "src.api.schemas.approval.ApprovalResponse.model_validate",
        return_value={"id": "approval-123"},
    ):
        await process_approval(
            approval_id="approval-123",
            request=request,
            current_user=current_user,
            service=service,
        )

    decision_request = service.process.await_args.kwargs["request"]

    assert decision_request.edited_payload == edited_payload
    assert decision_request.decision == request.decision
    assert decision_request.decision_reason == request.decision_reason


@pytest.mark.asyncio
async def test_process_approval_propagates_authorization_error() -> None:
    """
    It should propagate AuthorizationError from the service.
    """

    service = MagicMock(
        spec=ApprovalLifecycleService,
    )
    service.process = AsyncMock(
        side_effect=AuthorizationError(
            "Approval action is not authorized.",
        ),
    )

    current_user = build_current_user()

    request = ApprovalDecisionRequest(
        decision=ApprovalDecisionEnum.APPROVE,
        edited_payload=None,
        decision_reason="Approved.",
    )

    with pytest.raises(
        AuthorizationError,
        match="Approval action is not authorized.",
    ):
        await process_approval(
            approval_id="approval-123",
            request=request,
            current_user=current_user,
            service=service,
        )

    service.process.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_approval_propagates_unexpected_error() -> None:
    """
    It should propagate unexpected service failures.
    """

    service = MagicMock(
        spec=ApprovalLifecycleService,
    )
    service.process = AsyncMock(
        side_effect=RuntimeError(
            "Database unavailable.",
        ),
    )

    current_user = build_current_user()

    request = ApprovalDecisionRequest(
        decision=ApprovalDecisionEnum.APPROVE,
        edited_payload=None,
        decision_reason="Approved.",
    )

    with pytest.raises(
        RuntimeError,
        match="Database unavailable.",
    ):
        await process_approval(
            approval_id="approval-123",
            request=request,
            current_user=current_user,
            service=service,
        )

    service.process.assert_awaited_once()
