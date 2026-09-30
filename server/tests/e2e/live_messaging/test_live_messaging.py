"""
Live messaging: the approved-send path delivers for real, exactly as
often as the approval flow allows. Run before turning on
ENABLE_MESSAGING_TOOLS (docs/messaging-live-test.md).

Only the LLM calls are scripted (the planner, the agent's reasoning, the
answer judge), as in the other HITL e2e tests. The approval API, the
resume service, the gated tool, the approval-token check, the app's MCP
client and the MCP server's delivery are real, and every assertion counts
delivered messages (Mailpit, an IMAP inbox or a Slack channel) that carry
the test's own marker.

Skipped unless RUN_LIVE_MESSAGING=1, and always in CI.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, Response
from sqlalchemy import update

from adapters.persistence.sqlalchemy.models.agent_action import AgentAction
from adapters.persistence.sqlalchemy.repositories.agent_action import (
    AgentActionRepository,
)
from adapters.persistence.sqlalchemy.repositories.approval import ApprovalRepository
from adapters.persistence.sqlalchemy.session import session_factory
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision, AgentToolCall
from application.authorization.approval_lifecycle.verifier import TOOL_RESULT_KEY
from application.services import hitl_resume
from core.enums import AgentActionStatusEnum, ApprovalStatusEnum, HitlResumeStatusEnum
from tests.e2e.hitl_helpers import (
    final_decision,
    legal_agent_may_send,
    scripted_boundaries,
    start_pending_send,
)
from tests.e2e.live_messaging.conftest import Channel
from tests.e2e.live_messaging.verifiers import delivered

LIVE_ENABLED = os.getenv("RUN_LIVE_MESSAGING") == "1" and not os.getenv("CI")

pytestmark = [
    pytest.mark.live_messaging,
    pytest.mark.skipif(
        not LIVE_ENABLED,
        reason="live messaging tests run only with RUN_LIVE_MESSAGING=1, never in CI",
    ),
]


@pytest.fixture
def marker() -> str:
    return f"jlt-{uuid.uuid4().hex[:12]}"


@pytest_asyncio.fixture
async def pending_approval(
    channel: Channel,
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    marker: str,
) -> AsyncIterator[dict]:
    """
    A chat turn paused on the channel's send tool, with a draft carrying
    the marker. The reasoning script covers the pause and one resume.
    """

    send = AgentDecision(
        decision_type=AgentDecisionType.TOOL_CALL,
        reason="The user asked to send a message.",
        tool_call=AgentToolCall(tool_name=channel.tool_name, parameters=channel.parameters(marker)),
    )
    # The node replays from the top on each resume: the same send
    # decision again, then FINAL. Enough for a forced retry too.
    script = [send, send, final_decision(), send, final_decision()]

    async with legal_agent_may_send(channel.tool_name):
        with scripted_boundaries(script, None):
            approval = await start_pending_send(
                e2e_client, user=registered_user, conversation_id=conversation_id
            )
            assert approval["status"] == ApprovalStatusEnum.WAITING.value
            yield approval


async def _decide(client: AsyncClient, approval_id: str, user: dict, decision: str) -> Response:
    return await client.post(
        f"/api/v1/approvals/{approval_id}",
        json={"decision": decision},
        headers=user["headers"],
    )


async def _retry(
    client: AsyncClient, approval_id: str, user: dict, *, force: bool = False
) -> Response:
    return await client.post(
        f"/api/v1/approvals/{approval_id}/resume",
        params={"force": "true"} if force else None,
        headers=user["headers"],
    )


async def _action(approval_id: str) -> AgentAction:
    async with session_factory() as session:
        approval = await ApprovalRepository(session=session).get(approval_id)
        assert approval is not None
        action = await AgentActionRepository(session=session).get(approval.agent_action_id)
    assert action is not None
    return action


async def _set_action(approval_id: str, **values: Any) -> None:
    action = await _action(approval_id)
    async with session_factory() as session:
        await session.execute(
            update(AgentAction).where(AgentAction.id == action.id).values(**values)
        )
        await session.commit()


async def _assert_sent(approval_id: str) -> None:
    action = await _action(approval_id)
    assert action.status == AgentActionStatusEnum.COMPLETED
    assert TOOL_RESULT_KEY in (action.result or {})


@pytest.mark.asyncio
async def test_approve_delivers_exactly_one_message(
    channel: Channel,
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    marker: str,
) -> None:
    approval_id = pending_approval["approval_id"]

    approved = await _decide(e2e_client, approval_id, registered_user, "approve")

    assert approved.status_code == 200, approved.text
    assert approved.json()["data"]["resume_status"] == HitlResumeStatusEnum.COMPLETED.value
    assert await delivered(channel.verifier, marker, expected=1) == 1
    await _assert_sent(approval_id)


@pytest.mark.asyncio
async def test_two_concurrent_approvals_deliver_one_message(
    channel: Channel,
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    marker: str,
) -> None:
    approval_id = pending_approval["approval_id"]

    responses = await asyncio.gather(
        _decide(e2e_client, approval_id, registered_user, "approve"),
        _decide(e2e_client, approval_id, registered_user, "approve"),
    )

    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    assert await delivered(channel.verifier, marker, expected=1) == 1
    await _assert_sent(approval_id)


@pytest.mark.asyncio
async def test_concurrent_approve_and_reject_deliver_at_most_one_message(
    channel: Channel,
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    marker: str,
) -> None:
    approval_id = pending_approval["approval_id"]
    decisions = ["approve", "reject"]

    responses = await asyncio.gather(
        *(_decide(e2e_client, approval_id, registered_user, d) for d in decisions)
    )

    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    won = decisions[0 if responses[0].status_code == 200 else 1]
    expected_messages = 1 if won == "approve" else 0

    assert await delivered(channel.verifier, marker, expected=expected_messages) == (
        expected_messages
    )
    action = await _action(approval_id)
    assert action.status == (
        AgentActionStatusEnum.COMPLETED if won == "approve" else AgentActionStatusEnum.REJECTED
    )


@pytest.mark.asyncio
async def test_retry_after_sent_is_refused_and_sends_nothing(
    channel: Channel,
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    marker: str,
) -> None:
    approval_id = pending_approval["approval_id"]
    await _decide(e2e_client, approval_id, registered_user, "approve")
    assert await delivered(channel.verifier, marker, expected=1) == 1

    retried = await _retry(e2e_client, approval_id, registered_user)

    assert retried.status_code == 409, retried.text
    assert retried.json()["error"]["code"] == "APPROVAL_RESUME_NOT_ALLOWED"
    assert await delivered(channel.verifier, marker, expected=1) == 1


@pytest.mark.asyncio
async def test_a_stale_send_needs_force_and_then_sends_once_more(
    channel: Channel,
    e2e_client: AsyncClient,
    registered_user: dict,
    pending_approval: dict,
    marker: str,
) -> None:
    """
    A worker delivered the message, then stopped before storing the
    result: the action is left EXECUTING, long enough ago to be stale, with
    no recorded outcome. A retry needs the user's confirmation; a
    confirmed one sends again (the documented, accepted duplicate).
    """

    approval_id = pending_approval["approval_id"]
    await _decide(e2e_client, approval_id, registered_user, "approve")
    assert await delivered(channel.verifier, marker, expected=1) == 1

    await _set_action(
        approval_id,
        status=AgentActionStatusEnum.EXECUTING,
        result={},
        updated_at=datetime.now(UTC) - timedelta(hours=1),
    )

    unconfirmed = await _retry(e2e_client, approval_id, registered_user)

    assert unconfirmed.status_code == 409, unconfirmed.text
    error = unconfirmed.json()["error"]
    assert error["code"] == "APPROVAL_RESUME_NEEDS_CONFIRMATION"
    assert error["details"] == {"possibly_sent": True}
    assert await delivered(channel.verifier, marker, expected=1) == 1

    with patch.object(hitl_resume.logger, "warning", wraps=hitl_resume.logger.warning) as warning:
        confirmed = await _retry(e2e_client, approval_id, registered_user, force=True)

    assert confirmed.status_code == 200, confirmed.text
    assert await delivered(channel.verifier, marker, expected=2) == 2
    assert any("may be sent twice" in call.args[0] for call in warning.call_args_list)
    await _assert_sent(approval_id)
