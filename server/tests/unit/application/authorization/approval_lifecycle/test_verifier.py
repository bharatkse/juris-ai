"""
ApprovalRecordVerifier: an approval token covers exactly one decided
approval's action and payload, once.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from application.authorization.approval_lifecycle import verifier as verifier_module
from application.authorization.approval_lifecycle.verifier import (
    ApprovalRecordVerifier,
    approved_parameters,
)
from core.enums import AgentActionStatusEnum, ApprovalStatusEnum

TOKEN = "appr_" + "a" * 32
DRAFT = {"to": "client@example.org", "subject": "Notice", "body": "Please sign."}


def _approval(**overrides) -> SimpleNamespace:
    values = {
        "id": TOKEN,
        "agent_action_id": "actn_1",
        "status": ApprovalStatusEnum.APPROVED,
        "edited_payload": None,
    }
    return SimpleNamespace(**{**values, **overrides})


def _action(**overrides) -> SimpleNamespace:
    values = {
        "id": "actn_1",
        "tool_name": "email_send",
        "parameters": dict(DRAFT),
        "status": AgentActionStatusEnum.PENDING_APPROVAL,
        "result": None,
    }
    return SimpleNamespace(**{**values, **overrides})


@pytest.fixture
def records() -> dict:
    return {"approval": _approval(), "action": _action()}


@pytest.fixture
def verifier(records: dict):
    @asynccontextmanager
    async def session_factory():
        yield MagicMock()

    approvals = MagicMock()
    approvals.get = AsyncMock(side_effect=lambda approval_id: records["approval"])
    actions = MagicMock()
    actions.get = AsyncMock(side_effect=lambda action_id: records["action"])

    with (
        patch.object(verifier_module, "ApprovalRepository", return_value=approvals),
        patch.object(verifier_module, "AgentActionRepository", return_value=actions),
    ):
        yield ApprovalRecordVerifier(session_factory=session_factory)


async def _check(verifier, *, token=TOKEN, action="email_send", payload=None) -> bool:
    return await verifier.is_approved(
        token=token,
        action=action,
        payload=DRAFT if payload is None else payload,
    )


async def test_an_approved_exact_payload_is_accepted(verifier) -> None:
    assert await _check(verifier) is True


async def test_an_edited_payload_is_accepted_only_as_edited(verifier, records: dict) -> None:
    records["approval"] = _approval(
        status=ApprovalStatusEnum.EDITED,
        edited_payload={"body": "Please sign by Friday."},
    )

    assert await _check(verifier, payload={**DRAFT, "body": "Please sign by Friday."}) is True
    assert await _check(verifier) is False


@pytest.mark.parametrize(
    "status",
    [ApprovalStatusEnum.WAITING, ApprovalStatusEnum.REJECTED, ApprovalStatusEnum.EXPIRED],
)
async def test_an_undecided_or_rejected_approval_is_refused(
    verifier, records: dict, status: ApprovalStatusEnum
) -> None:
    records["approval"] = _approval(status=status)

    assert await _check(verifier) is False


async def test_an_unknown_or_empty_token_is_refused(verifier, records: dict) -> None:
    assert await _check(verifier, token="") is False

    records["approval"] = None
    assert await _check(verifier) is False


async def test_a_token_for_another_tool_is_refused(verifier) -> None:
    assert await _check(verifier, action="slack_post") is False


async def test_a_changed_payload_is_refused(verifier) -> None:
    assert await _check(verifier, payload={**DRAFT, "to": "attacker@example.org"}) is False


@pytest.mark.parametrize(
    "action",
    [
        _action(result={"tool_result": {"success": True}}),
        _action(status=AgentActionStatusEnum.COMPLETED),
        _action(status=AgentActionStatusEnum.REJECTED),
    ],
)
async def test_a_spent_token_is_refused(verifier, records: dict, action) -> None:
    records["action"] = action

    assert await _check(verifier) is False


def test_approved_parameters_apply_edits_over_the_proposal() -> None:
    assert approved_parameters(proposed=DRAFT, edited_payload=None) == DRAFT
    assert approved_parameters(proposed=DRAFT, edited_payload={"subject": "New"}) == {
        **DRAFT,
        "subject": "New",
    }
