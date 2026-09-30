"""
E2E: one chat request can't use more than TOKEN_QUOTA_PER_REQUEST
tokens (review R3). Before, only the daily quota existed: a single
request's tokens were bounded by iterations, tools and time, not tokens.

The quota is checked before each LLM call, in the real
LLMClient.generate(). A call that would cross it is never made; the
request fails with 413 REQUEST_TOKEN_QUOTA_EXCEEDED, and the tokens its
earlier calls used still reach usage_records (so the daily quota can't be
bypassed by requests that stop at the cap).

What's real: HTTP, JWT auth, Postgres, the planner and agent code paths,
the agent runtime (which turns a failed LLM call into a failed step), the
orchestrator, ChatService and UsageService. What's stubbed: each
provider's _generate() -- one level below the quota check -- and, as in
every e2e test, the guardrail judges (hermetic_llm).

Requires the real Postgres/Redis services with migrations applied. Run via
`make test-e2e`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from adapters.clients.llm.base import LLMClient
from adapters.clients.llm.groq import GroqClient
from adapters.clients.llm.local import LocalLLMClient
from adapters.persistence.sqlalchemy.models.conversation_event import ConversationEvent
from adapters.persistence.sqlalchemy.repositories.usage_record import UsageRecordRepository
from adapters.persistence.sqlalchemy.session import session_factory
from config.settings import get_settings
from core.constants import ERROR_REQUEST_TOKEN_QUOTA_EXCEEDED
from core.dto.clients.llm import LLMRequestDTO, LLMResponseDTO, LLMTokenUsageDTO

# Captured at import, before the hermetic_llm fixture replaces it.
REAL_GENERATE = LLMClient.generate

PLANNER = "ExecutionPlanResponseSchema"
MESSAGE = "What is an FIR?"
QUOTA = 50_000

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
ANSWER = "An FIR is the first information report of a cognizable offence."
DECISION = {"decision_type": "final", "final_response": ANSWER}


class _Provider:
    """Stands in for Groq and Ollama; records every call that reaches it."""

    def __init__(self) -> None:
        self.calls: list[str | None] = []
        self.planner_usage = LLMTokenUsageDTO(
            prompt_tokens=1000, completion_tokens=200, total_tokens=1200
        )
        self.agent_usage = LLMTokenUsageDTO(
            prompt_tokens=700, completion_tokens=100, total_tokens=800
        )

    async def generate(self, client: LLMClient, *, request: LLMRequestDTO) -> LLMResponseDTO:
        schema = (request.response_format or {}).get("json_schema", {}).get("name")
        self.calls.append(schema)

        content, usage = (
            (PLAN, self.planner_usage) if schema == PLANNER else (DECISION, self.agent_usage)
        )

        return LLMResponseDTO(
            content=json.dumps(content),
            provider=client.provider,
            model=client.model,
            usage=usage,
        )


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
def quota(monkeypatch: pytest.MonkeyPatch) -> int:
    settings = get_settings().rate_limit
    assert settings.RATE_LIMIT_ENABLED, "these tests need RATE_LIMIT_ENABLED"
    monkeypatch.setattr(settings, "TOKEN_QUOTA_PER_REQUEST", QUOTA)
    return QUOTA


async def _tokens_today(user_id: str) -> int:
    day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    async with session_factory() as session:
        return await UsageRecordRepository(session=session).get_daily_token_usage(
            user_id=user_id,
            window_start=day,
        )


async def _events(conversation_id: str) -> list[ConversationEvent]:
    async with session_factory() as session:
        result = await session.execute(
            select(ConversationEvent).where(ConversationEvent.conversation_id == conversation_id)
        )
        return list(result.scalars())


def _refused_by_quota(response) -> None:
    assert response.status_code == 413, response.text
    error = response.json()["error"]
    assert error["code"] == ERROR_REQUEST_TOKEN_QUOTA_EXCEEDED
    assert f"{QUOTA} tokens" in error["message"]


async def test_a_request_within_the_quota_is_answered(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    provider: _Provider,
) -> None:
    response = await e2e_client.post(
        "/api/v1/chat",
        data={"conversation_id": conversation_id, "message": MESSAGE},
        headers=registered_user["headers"],
    )

    assert response.status_code == 200, response.text
    # Every call went through: the planner and the agent.
    assert PLANNER in provider.calls and len(provider.calls) >= 2
    used = await _tokens_today(registered_user["user_id"])
    assert 0 < used <= QUOTA


async def test_a_request_whose_first_call_is_over_the_quota_makes_no_call(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    provider: _Provider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The planner's prompt alone is over a 10-token quota."""

    monkeypatch.setattr(get_settings().rate_limit, "TOKEN_QUOTA_PER_REQUEST", 10)

    response = await e2e_client.post(
        "/api/v1/chat",
        data={"conversation_id": conversation_id, "message": MESSAGE},
        headers=registered_user["headers"],
    )

    assert response.status_code == 413, response.text
    assert response.json()["error"]["code"] == ERROR_REQUEST_TOKEN_QUOTA_EXCEEDED
    assert provider.calls == []
    assert await _tokens_today(registered_user["user_id"]) == 0
    # The request failed as a whole: its USER message was rolled back.
    assert await _events(conversation_id) == []


async def test_a_call_that_would_cross_the_quota_mid_request_is_never_made(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    provider: _Provider,
) -> None:
    """
    The planner's call leaves 10 tokens: the agent's call is refused
    before it reaches the provider. The agent runtime turns that into a
    failed step, which would otherwise end as a 200 "something went
    wrong"; the request still stops with the quota error.
    """

    provider.planner_usage = LLMTokenUsageDTO(
        prompt_tokens=49_000, completion_tokens=990, total_tokens=QUOTA - 10
    )

    response = await e2e_client.post(
        "/api/v1/chat",
        data={"conversation_id": conversation_id, "message": MESSAGE},
        headers=registered_user["headers"],
    )

    _refused_by_quota(response)
    assert provider.calls == [PLANNER]
    # The planner's tokens were spent, so they count toward the daily quota.
    assert await _tokens_today(registered_user["user_id"]) == QUOTA - 10


async def test_a_streamed_request_ends_with_an_error_event(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    provider: _Provider,
) -> None:
    provider.planner_usage = LLMTokenUsageDTO(
        prompt_tokens=49_000, completion_tokens=990, total_tokens=QUOTA - 10
    )

    async with e2e_client.stream(
        "POST",
        "/api/v1/chat/stream",
        data={"conversation_id": conversation_id, "message": MESSAGE},
        headers=registered_user["headers"],
    ) as response:
        assert response.status_code == 200
        body = (await response.aread()).decode()

    events = [block for block in body.split("\n\n") if block.strip()]
    assert len(events) == 1, body
    name, data = events[0].split("\n", 1)
    assert name == "event: error"
    error = json.loads(data.removeprefix("data: "))
    assert error["code"] == ERROR_REQUEST_TOKEN_QUOTA_EXCEEDED
    assert ANSWER not in body

    assert provider.calls == [PLANNER]
    assert await _tokens_today(registered_user["user_id"]) == QUOTA - 10
