"""
E2E: user memory wired into the REAL chat flow, over real HTTP, real
Postgres, real Redis, the real LangGraph checkpointer -- not the
service layer directly (that is tests/e2e/test_user_memory_isolation.py
and test_user_memory_api.py). This is the verification pass the wiring
itself needs: ChatService._build_chat_request ->
UserMemoryService.retrieve_for_prompt -> OrchestratorRequest ->
ConversationContext/ConversationDTO -> the agent's built prompt, and
ChatService._persist_assistant_response -> MemoryExtractionScheduler,
all through the real dependency-injected app, not test doubles standing
in for any of those layers.

What's real: FastAPI routing/middleware/DI, JWT auth, Postgres (users,
conversations, conversation_events, user_memories), the real Postgres-
backed LangGraph checkpointer, the real execution graph, the real
UserMemoryService/UserMemoryRepository (real pgvector queries), and the
real prompt builder (agentic/agents/prompts/base.py's build_messages).

What's mocked, and why -- the same LLM-reasoning boundary every other
e2e test in this suite mocks, nothing more:
  - LLMPlanGenerator.generate() / BaseAgent._reason(): scripted to
    return a FINAL decision, capturing the AgentRequestDTO it was
    called with -- that captured request is this test's window into
    what the real prompt-building pipeline actually assembled.

Requires the real Postgres/Redis docker compose services running
(`./setup.sh --install --dependency postgres
--dependency redis`). Run via `make test-e2e`.
"""

from __future__ import annotations

import uuid
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from adapters.persistence.sqlalchemy.repositories.user_memory import (
    UserMemoryRepository,
)
from adapters.persistence.sqlalchemy.session import session_factory
from agentic.agents.base import BaseAgent
from agentic.agents.runtime.continuation import AgentContinuationService
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision
from agentic.evaluation.answer import AnswerEvaluationSummary
from agentic.planning.llm_planner import LLMPlanGenerator
from application.services.user_memory import expiry_from, hash_content
from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from core.enums import AgentTypeEnum, ExecutionModeEnum, IntentEnum, UserMemoryKindEnum
from main import app as fastapi_app

MEMORY_DIMENSION = 384
MEMORY_MODEL = "chat-wiring-test-model"
PROFILE_TEXT = "Practises before the Delhi High Court"


def _plan(*, message: str) -> ExecutionPlanDTO:
    return ExecutionPlanDTO(
        intent=IntentEnum.GENERAL,
        mode=ExecutionModeEnum.SEQUENTIAL,
        steps=(
            ExecutionStepDTO(
                id="step-1",
                agent=AgentTypeEnum.LEGAL,
                instruction=message,
                depends_on=(),
                stage=1,
                arguments={},
            ),
        ),
        metadata={},
    )


async def _seed_profile_memory(user_id: str, *, content: str = PROFILE_TEXT) -> str:
    """
    A PROFILE-kind memory: always included by retrieve_for_prompt
    regardless of similarity, so this doesn't depend on the app's real
    embedding model producing any particular score for ``content``.
    """

    now = datetime.now(UTC)

    async with session_factory() as session:
        memory = await UserMemoryRepository(session=session).add(
            user_id=user_id,
            kind=UserMemoryKindEnum.PROFILE,
            content=content,
            content_hash=hash_content(f"{user_id}:{content}"),
            embedding=[1.0] + [0.0] * (MEMORY_DIMENSION - 1),
            embedding_model=MEMORY_MODEL,
            confidence=1.0,
            last_used_at=now,
            expires_at=expiry_from(now),
        )
        await session.commit()

        return memory.id


async def _enable_memory(e2e_client: AsyncClient, headers: dict) -> None:
    response = await e2e_client.put(
        "/api/v1/memory/settings",
        json={"enabled": True},
        headers=headers,
    )
    assert response.status_code == 200, response.text


async def _second_user(e2e_client: AsyncClient) -> dict:
    email = f"e2e-chatmem-{uuid.uuid4().hex[:16]}@example.com"
    password = "Str0ng-E2E-Passw0rd!"

    register = await e2e_client.post(
        "/api/v1/users",
        json={
            "email": email,
            "password": password,
            "confirm_password": password,
            "first_name": "E2E",
            "last_name": "Second",
        },
    )
    assert register.status_code == 201, register.text
    user_id = register.json()["data"]["id"]

    login = await e2e_client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert login.status_code == 200, login.text
    body = login.json()
    token = (
        body["data"]["access_token"] if "data" in body and body["data"] else body["access_token"]
    )

    return {"user_id": user_id, "headers": {"Authorization": f"Bearer {token}"}}


async def _chat_and_capture_request(
    e2e_client: AsyncClient,
    *,
    conversation_id: str,
    message: str,
    headers: dict,
):
    """
    POST /chat through the real app, scripting only the LLM-reasoning
    boundary, and return the AgentRequestDTO BaseAgent._reason() was
    actually called with -- i.e. what the real wiring assembled.
    """

    captured: dict = {}

    final_decision = AgentDecision(
        decision_type=AgentDecisionType.FINAL,
        reason="Answering directly.",
        final_response="Here is the answer.",
    )

    async def fake_reason(self, *, request, context=()):
        captured["request"] = request
        return final_decision

    async def fake_plan_generate(self, *, request):
        return _plan(message=message)

    async def fake_gate_final(self, *, handle, result):
        # Answer-quality gating (a real Groq-backed judge call) is out
        # of scope for this test -- see test_hitl_approval_flow.py's
        # module docstring for the same pattern. Always accept.
        return None, AnswerEvaluationSummary(groundedness=0.95, relevance=0.90)

    async with AsyncExitStack() as patches:
        patches.enter_context(patch.object(LLMPlanGenerator, "generate", fake_plan_generate))
        patches.enter_context(patch.object(BaseAgent, "_reason", fake_reason))
        patches.enter_context(
            patch.object(AgentContinuationService, "_gate_final", fake_gate_final)
        )

        response = await e2e_client.post(
            "/api/v1/chat",
            data={"conversation_id": conversation_id, "message": message},
            headers=headers,
        )

    assert response.status_code == 200, response.text

    return captured["request"]


async def _create_conversation(e2e_client: AsyncClient, headers: dict) -> str:
    response = await e2e_client.post("/api/v1/conversations", json={}, headers=headers)
    assert response.status_code == 201, response.text

    return response.json()["data"]["id"]


# ----------------------------------------------------------------------
# Injection reaches the real, wired prompt -- and only the owner's turn
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_is_injected_into_the_real_chat_flow_and_scoped_to_its_owner(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
) -> None:
    other = await _second_user(e2e_client)

    await _enable_memory(e2e_client, registered_user["headers"])
    await _enable_memory(e2e_client, other["headers"])

    await _seed_profile_memory(registered_user["user_id"])

    other_conversation_id = await _create_conversation(e2e_client, other["headers"])

    owner_request = await _chat_and_capture_request(
        e2e_client,
        conversation_id=conversation_id,
        message="What should I know about my practice?",
        headers=registered_user["headers"],
    )
    other_request = await _chat_and_capture_request(
        e2e_client,
        conversation_id=other_conversation_id,
        message="What should I know about my practice?",
        headers=other["headers"],
    )

    # The owner's real, wired request carries the memory -- not smuggled
    # into history, on its own field.
    assert [item.content for item in owner_request.conversation.user_memory] == [PROFILE_TEXT]
    assert all(
        PROFILE_TEXT not in message.content for message in owner_request.conversation.messages
    )

    # The other real user's request, through the exact same wiring,
    # never sees it.
    assert other_request.conversation.user_memory == ()
    assert all(
        PROFILE_TEXT not in message.content for message in other_request.conversation.messages
    )


# ----------------------------------------------------------------------
# The conversation switch suppresses injection in the real chat flow
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_conversation_switch_suppresses_injection_in_the_real_chat_flow(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
) -> None:
    await _enable_memory(e2e_client, registered_user["headers"])
    await _seed_profile_memory(registered_user["user_id"])

    switch_response = await e2e_client.put(
        f"/api/v1/conversations/{conversation_id}/memory",
        json={"memory_disabled": True},
        headers=registered_user["headers"],
    )
    assert switch_response.status_code == 200, switch_response.text

    request = await _chat_and_capture_request(
        e2e_client,
        conversation_id=conversation_id,
        message="What should I know about my practice?",
        headers=registered_user["headers"],
    )

    assert request.conversation.user_memory == ()


# ----------------------------------------------------------------------
# The write hook actually fires from a real, committed chat turn
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_real_chat_turn_schedules_extraction_only_after_it_commits(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
) -> None:
    await _enable_memory(e2e_client, registered_user["headers"])

    scheduler = fastapi_app.state.memory_extraction_scheduler

    with patch.object(scheduler, "schedule") as mock_schedule:
        await _chat_and_capture_request(
            e2e_client,
            conversation_id=conversation_id,
            message="Hello there.",
            headers=registered_user["headers"],
        )

    mock_schedule.assert_called_once_with(
        user_id=registered_user["user_id"],
        conversation_id=conversation_id,
    )
