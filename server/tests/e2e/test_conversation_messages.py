"""
E2E: GET /conversations/{id}/messages returns a conversation's stored
messages, including the answer HitlResumeService saves after an approval
is decided -- which no other endpoint returns.

Same setup as test_hitl_approval_flow.py: real HTTP, JWT auth, Postgres,
the LangGraph checkpointer and HitlResumeService; the LLM calls, answer
judge and Gmail MCP hop are patched (tests/e2e/hitl_helpers.py).

Requires the real Postgres/Redis docker compose services running. Run via
`make test-e2e`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient

from adapters.persistence.sqlalchemy.repositories.conversation_event import (
    ConversationEventRepository,
)
from adapters.persistence.sqlalchemy.session import session_factory
from application.services.conversation_event import ConversationEventService
from core.enums import ApprovalStatusEnum, MessageRoleEnum
from tests.e2e.hitl_helpers import (
    CHAT_MESSAGE,
    FINAL_ANSWER,
    PENDING_APPROVAL_TEXT,
    approve_then_final_script,
    legal_agent_may_send,
    scripted_boundaries,
    start_pending_send,
)


@pytest_asyncio.fixture
async def legal_agent_send_policy() -> AsyncIterator[None]:
    async with legal_agent_may_send():
        yield


def _messages_url(conversation_id: str) -> str:
    return f"/api/v1/conversations/{conversation_id}/messages"


async def _seed_turns(conversation_id: str, questions: list[str]) -> None:
    """
    Store a question and an answer per entry, the way ChatService does,
    without running a chat turn (these tests are about reading them back).
    """

    async with session_factory() as session:
        service = ConversationEventService(
            session=session,
            repository=ConversationEventRepository(session=session),
        )

        for question in questions:
            request_id = uuid4()
            user_event = await service.create(
                conversation_id=conversation_id,
                request_id=request_id,
                role=MessageRoleEnum.USER,
                content=question,
            )
            await service.create(
                conversation_id=conversation_id,
                request_id=request_id,
                parent_event_id=user_event.id,
                role=MessageRoleEnum.ASSISTANT,
                content=f"Answer to: {question}",
            )

        await session.commit()


@pytest.mark.asyncio
async def test_a_resumed_answer_can_be_fetched_after_the_approval(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    legal_agent_send_policy: None,
) -> None:
    mcp_calls: list[dict[str, Any]] = []

    with scripted_boundaries(approve_then_final_script(), mcp_calls):
        approval = await start_pending_send(
            e2e_client, user=registered_user, conversation_id=conversation_id
        )

        approve = await e2e_client.post(
            f"/api/v1/approvals/{approval['approval_id']}",
            json={"decision": "approve"},
            headers=registered_user["headers"],
        )
        assert approve.status_code == 200, approve.text
        assert approve.json()["data"]["status"] == ApprovalStatusEnum.APPROVED.value
        assert approve.json()["data"]["resume_status"] == "completed"

    # The approval response carries the approval, not the answer.
    assert FINAL_ANSWER not in approve.text

    response = await e2e_client.get(
        _messages_url(conversation_id),
        headers=registered_user["headers"],
    )
    assert response.status_code == 200, response.text

    page = response.json()["data"]
    assert page["pagination"] == {"total": 3, "offset": 0, "limit": 20, "has_more": False}

    user_message, pending, resumed = page["items"]

    # Oldest first: the question, the pending-approval reply, the resumed answer.
    assert user_message["role"] == "user"
    assert user_message["content"] == CHAT_MESSAGE
    # ApiResponse leaves out null fields.
    assert "parent_event_id" not in user_message

    assert pending["role"] == "assistant"
    assert PENDING_APPROVAL_TEXT in pending["content"]
    assert pending["parent_event_id"] == user_message["id"]
    assert pending["metadata"]["approval"]["approval_id"] == approval["approval_id"]

    assert resumed["role"] == "assistant"
    assert resumed["content"] == FINAL_ANSWER
    # Like the pending reply, the resumed answer answers the user's message.
    assert resumed["parent_event_id"] == user_message["id"]
    assert resumed["metadata"]["resumed_agent_action_id"]
    assert resumed["conversation_id"] == conversation_id


@pytest.mark.asyncio
async def test_messages_are_paged_oldest_first(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
) -> None:
    await _seed_turns(conversation_id, ["What is an FIR?", "What is bail?"])

    first = await e2e_client.get(
        _messages_url(conversation_id),
        params={"offset": 0, "limit": 3},
        headers=registered_user["headers"],
    )
    second = await e2e_client.get(
        _messages_url(conversation_id),
        params={"offset": 3, "limit": 3},
        headers=registered_user["headers"],
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text

    first_page = first.json()["data"]
    second_page = second.json()["data"]

    assert first_page["pagination"] == {"total": 4, "offset": 0, "limit": 3, "has_more": True}
    assert second_page["pagination"] == {"total": 4, "offset": 3, "limit": 3, "has_more": False}

    items = first_page["items"] + second_page["items"]
    assert [item["role"] for item in items] == ["user", "assistant", "user", "assistant"]
    assert items[0]["content"] == "What is an FIR?"
    assert items[2]["content"] == "What is bail?"
    assert items[1]["parent_event_id"] == items[0]["id"]
    assert items[3]["parent_event_id"] == items[2]["id"]
    assert len({item["id"] for item in items}) == 4


@pytest.mark.asyncio
async def test_another_user_cannot_read_the_messages(
    e2e_client: AsyncClient,
    registered_user: dict,
    second_registered_user: dict,
    conversation_id: str,
) -> None:
    await _seed_turns(conversation_id, ["What is an FIR?"])

    # The owner can read them.
    own = await e2e_client.get(
        _messages_url(conversation_id),
        headers=registered_user["headers"],
    )
    assert own.status_code == 200, own.text
    assert own.json()["data"]["pagination"]["total"] == 2

    # Same answer GET /conversations/{id} gives another user.
    detail = await e2e_client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers=second_registered_user["headers"],
    )
    messages = await e2e_client.get(
        _messages_url(conversation_id),
        headers=second_registered_user["headers"],
    )

    assert detail.status_code == 404, detail.text
    assert messages.status_code == 404, messages.text
    assert "What is an FIR?" not in messages.text

    anonymous = await e2e_client.get(_messages_url(conversation_id))
    assert anonymous.status_code == 401, anonymous.text


@pytest.mark.asyncio
async def test_an_archived_conversation_is_refused_like_get(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
) -> None:
    archive = await e2e_client.delete(
        f"/api/v1/conversations/{conversation_id}",
        headers=registered_user["headers"],
    )
    assert archive.status_code == 204, archive.text

    detail = await e2e_client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers=registered_user["headers"],
    )
    messages = await e2e_client.get(
        _messages_url(conversation_id),
        headers=registered_user["headers"],
    )

    assert messages.status_code == detail.status_code, (detail.text, messages.text)
    assert messages.json()["error"]["code"] == detail.json()["error"]["code"]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
@pytest.mark.asyncio
async def test_out_of_range_paging_is_rejected(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    params: dict,
) -> None:
    response = await e2e_client.get(
        _messages_url(conversation_id),
        params=params,
        headers=registered_user["headers"],
    )

    assert response.status_code == 422, response.text
