"""
E2E: an approved send runs at most once when resumes overlap.

The decision and the retry endpoint can both start a resume of the same
action (a double-click, a client retry on timeout, two tabs). Only the
request that claims the action in the database (an atomic conditional
UPDATE, so it holds across workers) runs the send; any other gets a 409
or reports the resume as in progress.

The sender is the patched MCP hop from tests/e2e/hitl_helpers.py, made
slow here so the requests really overlap.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import update

from adapters.clients.mcp.registry import MCPServerRegistry
from adapters.persistence.sqlalchemy.models.agent_action import AgentAction
from adapters.persistence.sqlalchemy.models.approval import Approval
from adapters.persistence.sqlalchemy.repositories.agent_action import (
    AgentActionRepository,
)
from adapters.persistence.sqlalchemy.repositories.approval import ApprovalRepository
from adapters.persistence.sqlalchemy.session import session_factory
from core.enums import (
    AgentActionStatusEnum,
    ApprovalDecisionEnum,
    ApprovalStatusEnum,
    HitlResumeStatusEnum,
)
from tests.e2e.hitl_helpers import (
    approve_then_final_script,
    legal_agent_may_send,
    scripted_boundaries,
    start_pending_send,
)

SEND_SECONDS = 0.5


@pytest.fixture
def mcp_calls() -> list[dict[str, Any]]:
    return []


@pytest_asyncio.fixture
async def boundaries(mcp_calls: list[dict[str, Any]]) -> AsyncIterator[None]:
    async with legal_agent_may_send():
        with scripted_boundaries(approve_then_final_script(), mcp_calls):
            yield


@pytest_asyncio.fixture
async def pending_approval(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    boundaries: None,
) -> dict:
    approval = await start_pending_send(
        e2e_client, user=registered_user, conversation_id=conversation_id
    )
    assert approval["status"] == ApprovalStatusEnum.WAITING.value
    return approval


@pytest.fixture
def slow_sender(boundaries: None) -> Any:
    """
    Make the send slow, on top of the scripted MCP hop, so a second
    request arrives while the first is still sending.
    """

    scripted_call_tool = MCPServerRegistry.call_tool

    async def slow_call_tool(self, **kwargs):
        await asyncio.sleep(SEND_SECONDS)
        return await scripted_call_tool(self, **kwargs)

    with patch.object(MCPServerRegistry, "call_tool", slow_call_tool):
        yield


def _sends(mcp_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [call for call in mcp_calls if call["tool_name"] == "send_message"]


async def _approve(e2e_client: AsyncClient, approval_id: str, user: dict):
    return await e2e_client.post(
        f"/api/v1/approvals/{approval_id}",
        json={"decision": "approve"},
        headers=user["headers"],
    )


async def _retry(e2e_client: AsyncClient, approval_id: str, user: dict, *, force: bool = False):
    return await e2e_client.post(
        f"/api/v1/approvals/{approval_id}/resume",
        params={"force": "true"} if force else None,
        headers=user["headers"],
    )


async def _fetch_action(approval_id: str) -> AgentAction:
    async with session_factory() as session:
        approval = await ApprovalRepository(session=session).get(approval_id)
        assert approval is not None
        action = await AgentActionRepository(session=session).get(approval.agent_action_id)
    assert action is not None
    return action


async def _commit_decision_only(approval_id: str, user_id: str) -> None:
    """
    The state a crash leaves between the decision commit and the resume:
    the approval APPROVED, its action still PENDING_APPROVAL.
    """

    async with session_factory() as session:
        await session.execute(
            update(Approval)
            .where(Approval.id == approval_id)
            .values(
                status=ApprovalStatusEnum.APPROVED,
                decision_type=ApprovalDecisionEnum.APPROVE,
                approved_by=user_id,
                decided_at=datetime.now(UTC),
            )
        )
        await session.commit()


async def _set_action(approval_id: str, **values: Any) -> None:
    action = await _fetch_action(approval_id)
    async with session_factory() as session:
        await session.execute(
            update(AgentAction).where(AgentAction.id == action.id).values(**values)
        )
        await session.commit()


@pytest.mark.asyncio
async def test_concurrent_approvals_send_once(
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    slow_sender: None,
    mcp_calls: list[dict[str, Any]],
) -> None:
    approval_id = pending_approval["approval_id"]

    first, second = await asyncio.gather(
        _approve(e2e_client, approval_id, registered_user),
        _approve(e2e_client, approval_id, registered_user),
    )

    assert len(_sends(mcp_calls)) == 1
    # Only one decision is recorded; the other is refused as already decided.
    assert sorted(response.status_code for response in (first, second)) == [200, 409]
    winner = first if first.status_code == 200 else second
    loser = second if winner is first else first
    assert winner.json()["data"]["resume_status"] == HitlResumeStatusEnum.COMPLETED.value
    assert loser.json()["error"]["code"] == "APPROVAL_ALREADY_DECIDED"
    assert (await _fetch_action(approval_id)).status == AgentActionStatusEnum.COMPLETED


@pytest.mark.asyncio
@pytest.mark.parametrize("first_decision", ["approve", "reject"])
async def test_concurrent_approve_and_reject_one_wins(
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    slow_sender: None,
    mcp_calls: list[dict[str, Any]],
    first_decision: str,
) -> None:
    """
    Conflicting decisions at once: exactly one is recorded, the other gets
    409 with the approval's current status and changes nothing. Only a
    winning approve sends.
    """

    approval_id = pending_approval["approval_id"]
    decisions = [first_decision, "reject" if first_decision == "approve" else "approve"]

    responses = await asyncio.gather(
        *(
            e2e_client.post(
                f"/api/v1/approvals/{approval_id}",
                json={"decision": decision},
                headers=registered_user["headers"],
            )
            for decision in decisions
        )
    )

    assert sorted(response.status_code for response in responses) == [200, 409], [
        response.text for response in responses
    ]
    winner_index = 0 if responses[0].status_code == 200 else 1
    winner, loser = responses[winner_index], responses[1 - winner_index]
    won = decisions[winner_index]
    expected_status = (
        ApprovalStatusEnum.APPROVED if won == "approve" else ApprovalStatusEnum.REJECTED
    )

    assert winner.json()["data"]["status"] == expected_status.value
    error = loser.json()["error"]
    assert error["code"] == "APPROVAL_ALREADY_DECIDED"
    assert error["details"] == {"current_status": expected_status.value}

    async with session_factory() as session:
        stored = await ApprovalRepository(session=session).get(approval_id)
    assert stored is not None
    assert stored.status == expected_status
    assert len(_sends(mcp_calls)) == (1 if won == "approve" else 0)
    assert (await _fetch_action(approval_id)).status == (
        AgentActionStatusEnum.COMPLETED if won == "approve" else AgentActionStatusEnum.REJECTED
    )


@pytest.mark.asyncio
async def test_concurrent_retries_send_once(
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    slow_sender: None,
    mcp_calls: list[dict[str, Any]],
) -> None:
    approval_id = pending_approval["approval_id"]
    await _commit_decision_only(approval_id, registered_user["user_id"])

    first, second = await asyncio.gather(
        _retry(e2e_client, approval_id, registered_user),
        _retry(e2e_client, approval_id, registered_user),
    )

    assert len(_sends(mcp_calls)) == 1
    assert sorted(response.status_code for response in (first, second)) == [200, 409]
    winner = first if first.status_code == 200 else second
    loser = second if winner is first else first
    assert winner.json()["data"]["resume_status"] == HitlResumeStatusEnum.COMPLETED.value
    assert loser.json()["error"]["code"] == "APPROVAL_RESUME_NOT_ALLOWED"
    assert (await _fetch_action(approval_id)).status == AgentActionStatusEnum.COMPLETED


@pytest.mark.asyncio
async def test_retry_while_sending_is_refused(
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    slow_sender: None,
    mcp_calls: list[dict[str, Any]],
) -> None:
    approval_id = pending_approval["approval_id"]

    approve = asyncio.create_task(_approve(e2e_client, approval_id, registered_user))
    # Retry once the approve has claimed the action and is sending.
    for _ in range(50):
        await asyncio.sleep(SEND_SECONDS / 10)
        if (await _fetch_action(approval_id)).status == AgentActionStatusEnum.EXECUTING:
            break

    during = await _retry(e2e_client, approval_id, registered_user)
    approved = await approve

    assert during.status_code == 409, during.text
    assert during.json()["error"]["code"] == "APPROVAL_RESUME_NOT_ALLOWED"
    assert approved.json()["data"]["resume_status"] == HitlResumeStatusEnum.COMPLETED.value
    assert len(_sends(mcp_calls)) == 1


@pytest.mark.asyncio
async def test_retry_after_sent_is_refused(
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    mcp_calls: list[dict[str, Any]],
) -> None:
    approval_id = pending_approval["approval_id"]

    approved = await _approve(e2e_client, approval_id, registered_user)
    assert approved.json()["data"]["resume_status"] == HitlResumeStatusEnum.COMPLETED.value

    again = await _retry(e2e_client, approval_id, registered_user)

    assert again.status_code == 409, again.text
    assert again.json()["error"]["code"] == "APPROVAL_RESUME_NOT_ALLOWED"
    assert len(_sends(mcp_calls)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("force", [False, True])
async def test_a_recent_unfinished_send_is_not_retried(
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    mcp_calls: list[dict[str, Any]],
    force: bool,
) -> None:
    """
    An action claimed moments ago (EXECUTING, no stored result) may still
    be sending in another worker: a retry is refused, even with force.
    """

    approval_id = pending_approval["approval_id"]
    await _commit_decision_only(approval_id, registered_user["user_id"])
    await _set_action(
        approval_id,
        status=AgentActionStatusEnum.EXECUTING,
        updated_at=datetime.now(UTC),
    )

    retried = await _retry(e2e_client, approval_id, registered_user, force=force)

    assert retried.status_code == 409, retried.text
    assert retried.json()["error"]["code"] == "APPROVAL_RESUME_NOT_ALLOWED"
    assert _sends(mcp_calls) == []


async def _stuck_send(approval_id: str, user_id: str) -> None:
    """
    The worker that claimed the action stopped before any result was
    stored, longer ago than HITL_RESUME_STALE_SECONDS: the message may or
    may not have been sent.
    """

    await _commit_decision_only(approval_id, user_id)
    await _set_action(
        approval_id,
        status=AgentActionStatusEnum.EXECUTING,
        updated_at=datetime.now(UTC) - timedelta(hours=1),
    )


@pytest.mark.asyncio
async def test_a_stuck_send_needs_confirmation_before_it_is_retried(
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    mcp_calls: list[dict[str, Any]],
) -> None:
    approval_id = pending_approval["approval_id"]
    await _stuck_send(approval_id, registered_user["user_id"])

    retried = await _retry(e2e_client, approval_id, registered_user)

    assert retried.status_code == 409, retried.text
    error = retried.json()["error"]
    assert error["code"] == "APPROVAL_RESUME_NEEDS_CONFIRMATION"
    assert error["details"] == {"possibly_sent": True}
    assert _sends(mcp_calls) == []
    assert (await _fetch_action(approval_id)).status == AgentActionStatusEnum.EXECUTING


@pytest.mark.asyncio
async def test_a_confirmed_retry_of_a_stuck_send_sends_once(
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    slow_sender: None,
    mcp_calls: list[dict[str, Any]],
) -> None:
    approval_id = pending_approval["approval_id"]
    await _stuck_send(approval_id, registered_user["user_id"])

    first, second = await asyncio.gather(
        _retry(e2e_client, approval_id, registered_user, force=True),
        _retry(e2e_client, approval_id, registered_user, force=True),
    )

    assert sorted(response.status_code for response in (first, second)) == [200, 409]
    winner = first if first.status_code == 200 else second
    assert winner.json()["data"]["resume_status"] == HitlResumeStatusEnum.COMPLETED.value
    assert len(_sends(mcp_calls)) == 1
    assert (await _fetch_action(approval_id)).status == AgentActionStatusEnum.COMPLETED


@pytest.mark.asyncio
async def test_a_stuck_send_with_a_stored_result_is_not_sent_again(
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    mcp_calls: list[dict[str, Any]],
) -> None:
    """
    The worker stopped after the provider's result was stored (delivery
    confirmed): recovery reuses that result and never sends again.
    """

    approval_id = pending_approval["approval_id"]
    await _commit_decision_only(approval_id, registered_user["user_id"])
    stored_result = {
        "tool_name": "email_send",
        "success": True,
        "content": "Message sent.",
        "evidence": [],
        "execution_metadata": {},
        "error": None,
    }
    await _set_action(
        approval_id,
        status=AgentActionStatusEnum.EXECUTING,
        result={"tool_result": stored_result, "approval_id": approval_id},
        updated_at=datetime.now(UTC) - timedelta(hours=1),
    )

    retried = await _retry(e2e_client, approval_id, registered_user)

    assert retried.status_code == 200, retried.text
    assert retried.json()["data"]["resume_status"] == HitlResumeStatusEnum.COMPLETED.value
    assert _sends(mcp_calls) == []
