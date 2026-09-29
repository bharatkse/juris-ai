"""
E2E: an approval decision is durable on its own, independent of what
happens after it; and a decided approval whose resume didn't finish can
be retried by its owner without sending twice (R14).

Each test drives a real chat turn to a real pending approval, decides
it over real HTTP, then reads the approval back from Postgres in a
fresh session (not the request's session or objects), so what's
asserted is what was actually committed.

Patched, for the same reasons as test_hitl_approval_flow.py: the LLM
calls, the answer-quality gate and the Gmail MCP hop (see
tests/e2e/hitl_helpers.py). RBAC is real. Resume failures are injected
at two points: before the graph resumes (AIOrchestrator.resume raises)
and after it finished (writing the resumed answer fails).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import update

from adapters.persistence.sqlalchemy.models.agent_action import AgentAction
from adapters.persistence.sqlalchemy.models.approval import Approval
from adapters.persistence.sqlalchemy.models.user import User
from adapters.persistence.sqlalchemy.repositories.agent_action import (
    AgentActionRepository,
)
from adapters.persistence.sqlalchemy.repositories.approval import ApprovalRepository
from adapters.persistence.sqlalchemy.session import session_factory
from agentic.orchestration.orchestrator import AIOrchestrator
from application.services.conversation_event import ConversationEventService
from core.enums import (
    AgentActionStatusEnum,
    ApprovalDecisionEnum,
    ApprovalStatusEnum,
    HitlResumeStatusEnum,
)
from tests.e2e.hitl_helpers import (
    DRAFT,
    FINAL_ANSWER,
    approve_then_final_script,
    legal_agent_may_send,
    scripted_boundaries,
    start_pending_send,
)

SENT_ONCE = [{"server_name": "gmail", "tool_name": "send_message", "arguments": DRAFT}]


@pytest.fixture
def mcp_calls() -> list[dict[str, Any]]:
    return []


@pytest_asyncio.fixture
async def boundaries(mcp_calls: list[dict[str, Any]]) -> AsyncIterator[None]:
    """
    Legal may send; the LLM, judge and MCP boundaries are scripted for
    one send that is approved and then answered.
    """

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
    """
    A real WAITING approval owned by registered_user.
    """

    approval = await start_pending_send(
        e2e_client, user=registered_user, conversation_id=conversation_id
    )
    assert approval["status"] == ApprovalStatusEnum.WAITING.value
    return approval


async def _fetch_approval(approval_id: str) -> Approval:
    async with session_factory() as session:
        approval = await ApprovalRepository(session=session).get(approval_id)
    assert approval is not None
    return approval


@pytest.mark.asyncio
async def test_edit_is_committed(
    e2e_client: AsyncClient, registered_user: dict, pending_approval: dict
) -> None:
    approval_id = pending_approval["approval_id"]

    response = await e2e_client.post(
        f"/api/v1/approvals/{approval_id}",
        json={"decision": "edit", "edited_payload": {"subject": "Case 84022"}},
        headers=registered_user["headers"],
    )

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["status"] == ApprovalStatusEnum.EDITED.value
    assert body["resume_status"] == HitlResumeStatusEnum.COMPLETED.value

    stored = await _fetch_approval(approval_id)
    assert stored.status == ApprovalStatusEnum.EDITED
    assert stored.edited_payload == {"subject": "Case 84022"}
    assert stored.decided_at is not None


@pytest.mark.asyncio
async def test_approve_survives_resume_failure(
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    mcp_calls: list[dict[str, Any]],
) -> None:
    approval_id = pending_approval["approval_id"]

    async def failing_resume(self, **kwargs):
        raise RuntimeError("resume failed")

    with patch.object(AIOrchestrator, "resume", failing_resume):
        response = await e2e_client.post(
            f"/api/v1/approvals/{approval_id}",
            json={"decision": "approve"},
            headers=registered_user["headers"],
        )

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["status"] == ApprovalStatusEnum.APPROVED.value
    assert body["resume_status"] == HitlResumeStatusEnum.FAILED.value

    stored = await _fetch_approval(approval_id)
    assert stored.status == ApprovalStatusEnum.APPROVED
    assert stored.approved_by == registered_user["user_id"]

    # The failure itself is recorded on the action, not only logged.
    async with session_factory() as session:
        action = await AgentActionRepository(session=session).get(stored.agent_action_id)
    assert action is not None
    assert action.status == AgentActionStatusEnum.FAILED
    assert action.result is not None
    assert action.result.get("error") == "RuntimeError"

    # The email went out before the resume failed, and its result is kept
    # on the action so a retry doesn't send it again.
    assert mcp_calls == SENT_ONCE
    assert action.result["tool_result"]["success"] is True

    # Deciding again is refused as already decided, not re-applied.
    again = await e2e_client.post(
        f"/api/v1/approvals/{approval_id}",
        json={"decision": "reject"},
        headers=registered_user["headers"],
    )
    assert again.status_code == 409, again.text


@pytest.mark.asyncio
async def test_expired_status_is_committed(
    e2e_client: AsyncClient, registered_user: dict, pending_approval: dict
) -> None:
    approval_id = pending_approval["approval_id"]

    async with session_factory() as session:
        await session.execute(
            update(Approval)
            .where(Approval.id == approval_id)
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()

    response = await e2e_client.post(
        f"/api/v1/approvals/{approval_id}",
        json={"decision": "approve"},
        headers=registered_user["headers"],
    )

    assert response.status_code == 410, response.text

    stored = await _fetch_approval(approval_id)
    assert stored.status == ApprovalStatusEnum.EXPIRED


async def _fetch_action(approval_id: str) -> AgentAction:
    approval = await _fetch_approval(approval_id)
    async with session_factory() as session:
        action = await AgentActionRepository(session=session).get(approval.agent_action_id)
    assert action is not None
    return action


async def _retry(e2e_client: AsyncClient, approval_id: str, user: dict):
    return await e2e_client.post(
        f"/api/v1/approvals/{approval_id}/resume",
        headers=user["headers"],
    )


@pytest.mark.asyncio
async def test_retry_after_failed_resume_completes_without_resending(
    e2e_client: AsyncClient,
    registered_user: dict,
    second_registered_user: dict,
    pending_approval: dict,
    mcp_calls: list[dict[str, Any]],
) -> None:
    """
    R14: the resume failed before the graph resumed. Only the owner may
    retry; the retry finishes the turn with the stored send result and
    never sends again; a second retry is refused.
    """

    approval_id = pending_approval["approval_id"]

    async def failing_resume(self, **kwargs):
        raise RuntimeError("resume failed")

    with patch.object(AIOrchestrator, "resume", failing_resume):
        first = await e2e_client.post(
            f"/api/v1/approvals/{approval_id}",
            json={"decision": "approve"},
            headers=registered_user["headers"],
        )
    assert first.json()["data"]["resume_status"] == HitlResumeStatusEnum.FAILED.value
    assert mcp_calls == SENT_ONCE

    forbidden = await _retry(e2e_client, approval_id, second_registered_user)
    assert forbidden.status_code == 403, forbidden.text

    retried = await _retry(e2e_client, approval_id, registered_user)
    assert retried.status_code == 200, retried.text
    assert retried.json()["data"]["resume_status"] == HitlResumeStatusEnum.COMPLETED.value

    assert mcp_calls == SENT_ONCE
    action = await _fetch_action(approval_id)
    assert action.status == AgentActionStatusEnum.COMPLETED
    assert action.result["content"] == FINAL_ANSWER

    again = await _retry(e2e_client, approval_id, registered_user)
    assert again.status_code == 409, again.text
    assert again.json()["error"]["code"] == "APPROVAL_RESUME_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_retry_after_the_graph_finished_does_not_rerun_the_turn(
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    mcp_calls: list[dict[str, Any]],
) -> None:
    """
    R14: the graph resumed and finished (its checkpoint advanced), then
    writing the answer failed. A retry must neither send again nor
    re-run the agent: the script has no reasoning calls left, so an
    extra one fails the test.
    """

    approval_id = pending_approval["approval_id"]
    original_create = ConversationEventService.create

    async def failing_resumed_event(self, **kwargs):
        if (kwargs.get("metadata") or {}).get("resumed_agent_action_id"):
            raise RuntimeError("event write failed")
        return await original_create(self, **kwargs)

    with patch.object(ConversationEventService, "create", failing_resumed_event):
        first = await e2e_client.post(
            f"/api/v1/approvals/{approval_id}",
            json={"decision": "approve"},
            headers=registered_user["headers"],
        )
    assert first.json()["data"]["resume_status"] == HitlResumeStatusEnum.FAILED.value

    retried = await _retry(e2e_client, approval_id, registered_user)
    assert retried.status_code == 200, retried.text
    assert retried.json()["data"]["resume_status"] == HitlResumeStatusEnum.COMPLETED.value

    assert mcp_calls == SENT_ONCE
    action = await _fetch_action(approval_id)
    assert action.status == AgentActionStatusEnum.COMPLETED
    assert action.result["content"] == FINAL_ANSWER


@pytest.mark.asyncio
async def test_retry_recovers_an_action_left_pending_by_a_crash(
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    mcp_calls: list[dict[str, Any]],
) -> None:
    """
    R14: the process stopped after committing the decision but before
    the resume ran -- the approval is APPROVED and the action is still
    PENDING_APPROVAL, with no failure recorded. Simulated by committing
    the decision straight to the database.
    """

    approval_id = pending_approval["approval_id"]

    async with session_factory() as session:
        await session.execute(
            update(Approval)
            .where(Approval.id == approval_id)
            .values(
                status=ApprovalStatusEnum.APPROVED,
                decision_type=ApprovalDecisionEnum.APPROVE,
                approved_by=registered_user["user_id"],
                decided_at=datetime.now(UTC),
            )
        )
        await session.commit()

    assert (await _fetch_action(approval_id)).status == AgentActionStatusEnum.PENDING_APPROVAL

    retried = await _retry(e2e_client, approval_id, registered_user)
    assert retried.status_code == 200, retried.text
    assert retried.json()["data"]["resume_status"] == HitlResumeStatusEnum.COMPLETED.value
    assert mcp_calls == SENT_ONCE


@pytest.mark.asyncio
async def test_retry_of_an_undecided_approval_is_refused(
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    mcp_calls: list[dict[str, Any]],
) -> None:
    response = await _retry(e2e_client, pending_approval["approval_id"], registered_user)

    assert response.status_code == 409, response.text
    assert mcp_calls == []


async def _set_role(user_id: str, role: str) -> None:
    async with session_factory() as session:
        await session.execute(update(User).where(User.id == user_id).values(role=role))
        await session.commit()


@pytest.mark.asyncio
async def test_a_user_demoted_after_approving_cannot_send_on_retry(
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    mcp_calls: list[dict[str, Any]],
) -> None:
    """
    Permission is re-checked when the approved send is about to run, not
    only when the approval was created: a member approves, the resume
    fails before the send, the user is demoted to reader, and the retry
    must not send.
    """

    approval_id = pending_approval["approval_id"]

    async def failing_before_send(self, **kwargs):
        raise RuntimeError("resume failed before the send")

    with patch.object(AIOrchestrator, "run_approved_tool", failing_before_send):
        first = await e2e_client.post(
            f"/api/v1/approvals/{approval_id}",
            json={"decision": "approve"},
            headers=registered_user["headers"],
        )
    assert first.json()["data"]["resume_status"] == HitlResumeStatusEnum.FAILED.value
    assert mcp_calls == []

    await _set_role(registered_user["user_id"], "reader")

    retried = await _retry(e2e_client, approval_id, registered_user)

    assert retried.status_code == 200, retried.text
    assert mcp_calls == []

    action = await _fetch_action(approval_id)
    assert action.result["tool_result"]["success"] is False
    assert action.result["tool_result"]["execution_metadata"]["error_type"] == "PermissionDenied"

    # Denied for good: a later retry is refused and still sends nothing.
    again = await _retry(e2e_client, approval_id, registered_user)
    assert again.status_code == 409, again.text
    assert mcp_calls == []


@pytest.mark.asyncio
async def test_a_user_demoted_before_approving_cannot_send(
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    mcp_calls: list[dict[str, Any]],
) -> None:
    await _set_role(registered_user["user_id"], "reader")

    response = await e2e_client.post(
        f"/api/v1/approvals/{pending_approval['approval_id']}",
        json={"decision": "approve"},
        headers=registered_user["headers"],
    )

    assert response.status_code == 200, response.text
    assert mcp_calls == []


@pytest.mark.asyncio
async def test_a_stored_send_is_reused_even_after_demotion(
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    mcp_calls: list[dict[str, Any]],
) -> None:
    """
    The send already happened before the resume failed; the retry only
    finishes the turn with the stored result, which is not a new action,
    so a demotion in between doesn't block it (and nothing is resent).
    """

    approval_id = pending_approval["approval_id"]

    async def failing_resume(self, **kwargs):
        raise RuntimeError("resume failed after the send")

    with patch.object(AIOrchestrator, "resume", failing_resume):
        await e2e_client.post(
            f"/api/v1/approvals/{approval_id}",
            json={"decision": "approve"},
            headers=registered_user["headers"],
        )
    assert mcp_calls == SENT_ONCE

    await _set_role(registered_user["user_id"], "reader")

    retried = await _retry(e2e_client, approval_id, registered_user)

    assert retried.status_code == 200, retried.text
    assert retried.json()["data"]["resume_status"] == HitlResumeStatusEnum.COMPLETED.value
    assert mcp_calls == SENT_ONCE
