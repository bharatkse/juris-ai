"""
E2E: the HITL send flow, over real HTTP, real Postgres, real Redis.

auth -> chat asks to email the client -> the agent proposes an
email_send draft -> the turn pauses and tells the user it needs their
approval -> POST /approvals/{id} (approve / edit / reject) -> the
approved (or edited) draft is sent exactly once, or nothing is sent ->
the conversation shows the outcome.

What's real: routing, JWT auth, RBAC (the default "member" role),
Postgres (users, conversations, agent_policies, agent_actions,
approvals), the Postgres LangGraph checkpointer, the execution graph,
ToolExecutionService, the real EmailSendTool and its
ApprovalRecordVerifier, ApprovalLifecycleService and HitlResumeService.
What's patched (LLM calls, answer judge, the Gmail MCP hop): see
tests/e2e/hitl_helpers.py.

Before the S4 fix an "approved send" ran the email tool's read path (a
mail search) and nothing was sent; before A5 the RBAC stub refused
every real user, so this test had to patch RBAC out.

Requires the real Postgres/Redis docker compose services running
(`./setup.sh --install --dependency postgres
--dependency redis`). Run via `make test-e2e`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from httpx import AsyncClient

from adapters.persistence.sqlalchemy.repositories.conversation_event import (
    ConversationEventRepository,
)
from adapters.persistence.sqlalchemy.session import session_factory
from application.services.conversation_event import ConversationEventService
from core.enums import ApprovalStatusEnum
from tests.e2e.hitl_helpers import (
    DRAFT,
    FINAL_ANSWER,
    approve_then_final_script,
    legal_agent_may_send,
    scripted_boundaries,
    start_pending_send,
)

# tests/conftest.py's pytest_collection_modifyitems auto-tags every
# test under tests/e2e/ with the "e2e" marker — no pytestmark needed
# here, matching the existing unit/smoke convention.


@pytest_asyncio.fixture
async def legal_agent_send_policy() -> AsyncIterator[None]:
    async with legal_agent_may_send():
        yield


async def _resumed_events(conversation_id: str) -> list:
    # Reads the rows HitlResumeService just wrote. Fetching them over
    # HTTP is covered by test_conversation_messages.py.
    async with session_factory() as session:
        events = await ConversationEventService(
            session=session,
            repository=ConversationEventRepository(session=session),
        ).list(conversation_id=conversation_id, limit=20)

    return [
        event for event in events if (event.event_metadata or {}).get("resumed_agent_action_id")
    ]


@pytest.mark.asyncio
async def test_approved_draft_is_sent_exactly_once(
    e2e_client: AsyncClient,
    registered_user: dict,
    second_registered_user: dict,
    conversation_id: str,
    legal_agent_send_policy: None,
) -> None:
    mcp_calls: list[dict[str, Any]] = []

    with scripted_boundaries(approve_then_final_script(), mcp_calls):
        approval = await start_pending_send(
            e2e_client, user=registered_user, conversation_id=conversation_id
        )
        assert approval["status"] == ApprovalStatusEnum.WAITING.value
        approval_id = approval["approval_id"]

        # Nothing is sent before a human decides.
        assert mcp_calls == []

        # Another user can't decide it -- approve, reject or edit -- and
        # nothing is sent.
        for other_decision in (
            {"decision": "approve"},
            {"decision": "reject"},
            {"decision": "edit", "edited_payload": {"to": "attacker@example.org"}},
        ):
            forbidden = await e2e_client.post(
                f"/api/v1/approvals/{approval_id}",
                json=other_decision,
                headers=second_registered_user["headers"],
            )
            assert forbidden.status_code == 403, forbidden.text
        assert mcp_calls == []

        approve = await e2e_client.post(
            f"/api/v1/approvals/{approval_id}",
            json={"decision": "approve"},
            headers=registered_user["headers"],
        )
        assert approve.status_code == 200, approve.text
        body = approve.json()["data"]
        assert body["status"] == ApprovalStatusEnum.APPROVED.value
        assert body["resume_status"] == "completed"

    # Sent, exactly once, exactly as proposed -- despite the replayed
    # reasoning call on resume.
    assert mcp_calls == [{"server_name": "gmail", "tool_name": "send_message", "arguments": DRAFT}]

    resumed = await _resumed_events(conversation_id)
    assert len(resumed) == 1
    assert resumed[0].content == FINAL_ANSWER


@pytest.mark.asyncio
async def test_edited_draft_is_sent_as_edited(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    legal_agent_send_policy: None,
) -> None:
    """
    An EDIT used to leave the conversation paused for good (NOT_RESUMED).
    """

    mcp_calls: list[dict[str, Any]] = []
    edited_body = "Please sign the agreement by Friday."

    with scripted_boundaries(approve_then_final_script(), mcp_calls):
        approval = await start_pending_send(
            e2e_client, user=registered_user, conversation_id=conversation_id
        )

        edit = await e2e_client.post(
            f"/api/v1/approvals/{approval['approval_id']}",
            json={"decision": "edit", "edited_payload": {"body": edited_body}},
            headers=registered_user["headers"],
        )
        assert edit.status_code == 200, edit.text
        assert edit.json()["data"]["status"] == ApprovalStatusEnum.EDITED.value
        assert edit.json()["data"]["resume_status"] == "completed"

    assert mcp_calls == [
        {
            "server_name": "gmail",
            "tool_name": "send_message",
            "arguments": {**DRAFT, "body": edited_body},
        }
    ]
    assert len(await _resumed_events(conversation_id)) == 1


@pytest.mark.asyncio
async def test_rejected_draft_is_never_sent(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    legal_agent_send_policy: None,
) -> None:
    mcp_calls: list[dict[str, Any]] = []

    # On reject the replayed send decision gets the rejection back and the
    # turn ends without FINAL, so only two reasoning calls happen.
    with scripted_boundaries(approve_then_final_script()[:2], mcp_calls):
        approval = await start_pending_send(
            e2e_client, user=registered_user, conversation_id=conversation_id
        )

        reject = await e2e_client.post(
            f"/api/v1/approvals/{approval['approval_id']}",
            json={"decision": "reject"},
            headers=registered_user["headers"],
        )
        assert reject.status_code == 200, reject.text
        assert reject.json()["data"]["resume_status"] == "completed"

    assert mcp_calls == []

    resumed = await _resumed_events(conversation_id)
    assert len(resumed) == 1
    assert "not approved" in resumed[0].content
