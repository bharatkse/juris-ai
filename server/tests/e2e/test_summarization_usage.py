"""
E2E: conversation summarization is part of the user's request (review
G1). Before the fix its LLM call ran before the request's usage scope,
token quota and deadline: its tokens never reached usage_records, the
per-request quota didn't see them, and a hung call held the request.

A conversation with more than UNSUMMARIZED_EVENT_LIMIT unsummarized
events triggers summarization on the next turn. The provider calls are
stubbed one level down, at each client's _generate(), so the real
LLMClient.generate() -- where the quota is checked and usage counted --
runs for summarization, the planner and the agent.

Requires the real Postgres/Redis services with migrations applied. Run via
`make test-e2e`.
"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient

from adapters.clients.llm.base import LLMClient
from adapters.clients.llm.groq import GroqClient
from adapters.clients.llm.local import LocalLLMClient
from adapters.persistence.sqlalchemy.repositories.conversation_event import (
    ConversationEventRepository,
)
from adapters.persistence.sqlalchemy.repositories.usage_record import UsageRecordRepository
from adapters.persistence.sqlalchemy.session import session_factory
from application.services.conversation_event import ConversationEventService
from application.services.conversation_summarization import UNSUMMARIZED_EVENT_LIMIT
from config.settings import get_settings
from core.constants import ERROR_REQUEST_TOKEN_QUOTA_EXCEEDED
from core.dto.clients.llm import LLMRequestDTO, LLMResponseDTO, LLMTokenUsageDTO
from core.enums import MessageRoleEnum

# Captured at import, before the hermetic_llm fixture replaces it.
REAL_GENERATE = LLMClient.generate

SUMMARY_USAGE = LLMTokenUsageDTO(prompt_tokens=900, completion_tokens=100, total_tokens=1000)
PLANNER_USAGE = LLMTokenUsageDTO(prompt_tokens=1000, completion_tokens=200, total_tokens=1200)
AGENT_USAGE = LLMTokenUsageDTO(prompt_tokens=700, completion_tokens=100, total_tokens=800)

PLAN = {
    "intent": "general",
    "mode": "sequential",
    "steps": [
        {
            "id": "step-1",
            "agent": "legal",
            "instruction": "Answer the question.",
            "depends_on": [],
            "stage": 1,
            "arguments": {},
        }
    ],
    "metadata": {},
}
DECISION = {
    "decision_type": "final",
    "final_response": "An FIR is the first information report of a cognizable offence.",
}
SUMMARY = "The user asked about criminal procedure; an FIR was explained."


def _is_summarization(request: LLMRequestDTO) -> bool:
    return request.messages[0].content.startswith("You compress conversation history")


class _Provider:
    """Stands in for Groq and Ollama; records every call it answers."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.summarization_delay = 0.0

    async def generate(self, client: LLMClient, *, request: LLMRequestDTO) -> LLMResponseDTO:
        if _is_summarization(request):
            self.calls.append("summarization")
            await asyncio.sleep(self.summarization_delay)
            content, usage = SUMMARY, SUMMARY_USAGE
        elif (request.response_format or {}).get("json_schema", {}).get(
            "name"
        ) == "ExecutionPlanResponseSchema":
            self.calls.append("planner")
            content, usage = json.dumps(PLAN), PLANNER_USAGE
        else:
            self.calls.append("agent")
            content, usage = json.dumps(DECISION), AGENT_USAGE

        return LLMResponseDTO(
            content=content,
            provider=client.provider,
            model=client.model,
            usage=usage,
        )

    def expected(self) -> int:
        """Total tokens of the calls answered so far."""

        per_call = {
            "summarization": SUMMARY_USAGE.total_tokens,
            "planner": PLANNER_USAGE.total_tokens,
            "agent": AGENT_USAGE.total_tokens,
        }
        return sum(per_call[call] for call in self.calls)


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> _Provider:
    provider = _Provider()

    async def _generate(self, *, request):
        return await provider.generate(self, request=request)

    monkeypatch.setattr(LLMClient, "generate", REAL_GENERATE)
    monkeypatch.setattr(GroqClient, "_generate", _generate)
    monkeypatch.setattr(LocalLLMClient, "_generate", _generate)
    return provider


@pytest.fixture(autouse=True)
def _rate_limit_on() -> None:
    assert get_settings().rate_limit.RATE_LIMIT_ENABLED, "these tests need RATE_LIMIT_ENABLED"


async def _seed_long_history(conversation_id: str) -> None:
    """More unsummarized events than UNSUMMARIZED_EVENT_LIMIT, stored as ChatService does."""

    async with session_factory() as session:
        service = ConversationEventService(
            session=session,
            repository=ConversationEventRepository(session=session),
        )

        for turn in range(UNSUMMARIZED_EVENT_LIMIT // 2 + 3):
            request_id = uuid4()
            user_event = await service.create(
                conversation_id=conversation_id,
                request_id=request_id,
                role=MessageRoleEnum.USER,
                content=f"Question {turn} about criminal procedure.",
            )
            await service.create(
                conversation_id=conversation_id,
                request_id=request_id,
                parent_event_id=user_event.id,
                role=MessageRoleEnum.ASSISTANT,
                content=f"Answer {turn}.",
            )

        await session.commit()


async def _tokens_today(user_id: str) -> int:
    day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    async with session_factory() as session:
        return await UsageRecordRepository(session=session).get_daily_token_usage(
            user_id=user_id,
            window_start=day,
        )


async def _chat(e2e_client: AsyncClient, user: dict, conversation_id: str):
    return await e2e_client.post(
        "/api/v1/chat",
        data={"conversation_id": conversation_id, "message": "What is an FIR?"},
        headers=user["headers"],
    )


async def test_a_long_conversation_records_the_summarization_tokens(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    provider: _Provider,
) -> None:
    await _seed_long_history(conversation_id)

    response = await _chat(e2e_client, registered_user, conversation_id)

    assert response.status_code == 200, response.text
    assert provider.calls[:2] == ["summarization", "planner"]
    assert await _tokens_today(registered_user["user_id"]) == provider.expected()


async def test_summarization_tokens_count_toward_the_per_request_quota(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    provider: _Provider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The turn fits a 3,800-token quota on its own (planner 1,200 used, the
    agent's prompt about 2,200), but not after summarization's 1,000: the
    agent call is refused before it is made, 413, and the summarization
    and planner tokens are still recorded.
    """

    await _seed_long_history(conversation_id)
    monkeypatch.setattr(get_settings().rate_limit, "TOKEN_QUOTA_PER_REQUEST", 3_800)

    response = await _chat(e2e_client, registered_user, conversation_id)

    assert response.status_code == 413, response.text
    assert response.json()["error"]["code"] == ERROR_REQUEST_TOKEN_QUOTA_EXCEEDED
    assert provider.calls == ["summarization", "planner"]
    assert await _tokens_today(registered_user["user_id"]) == (
        SUMMARY_USAGE.total_tokens + PLANNER_USAGE.total_tokens
    )


async def test_a_hung_summarization_is_cut_off_and_the_turn_still_answers(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    provider: _Provider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed_long_history(conversation_id)
    monkeypatch.setattr(get_settings().llm, "SUMMARIZATION_TIMEOUT_S", 0.5)
    provider.summarization_delay = 60

    started = time.monotonic()
    response = await _chat(e2e_client, registered_user, conversation_id)

    assert response.status_code == 200, response.text
    assert time.monotonic() - started < 30
    assert provider.calls[:2] == ["summarization", "planner"]
    # The cut-off call reported no usage; the rest of the turn did.
    assert await _tokens_today(registered_user["user_id"]) == (
        PLANNER_USAGE.total_tokens + provider.calls.count("agent") * AGENT_USAGE.total_tokens
    )
