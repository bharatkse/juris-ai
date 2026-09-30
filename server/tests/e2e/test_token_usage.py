"""
E2E: a real chat turn's token usage reaches usage_records, so the daily
token quota advances and is enforced from real traffic (review R3).

Before the fix a turn's usage was summed from AgentResponseDTO.usage,
which nothing set: every turn recorded 0 tokens and the quota only ever
moved in tests that wrote usage_records directly.

The provider calls themselves are stubbed one level down, at each
client's _generate(), so the real LLMClient.generate() -- where every
call's usage is counted -- runs for the planner and the agent. The
harmful-content judge stays stubbed above that level (hermetic_llm), so
it isn't counted here.

Requires the real Postgres/Redis services with migrations applied. Run via
`make test-e2e`.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from adapters.clients.llm.base import LLMClient
from adapters.clients.llm.groq import GroqClient
from adapters.clients.llm.local import LocalLLMClient
from adapters.persistence.sqlalchemy.repositories.usage_record import UsageRecordRepository
from adapters.persistence.sqlalchemy.session import session_factory
from config.settings import get_settings
from core.constants import ERROR_TOKEN_QUOTA_EXCEEDED
from core.dto.clients.llm import LLMRequestDTO, LLMResponseDTO, LLMTokenUsageDTO

# Captured at import, before the hermetic_llm fixture replaces it.
REAL_GENERATE = LLMClient.generate

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


class _Provider:
    """Stands in for Groq and Ollama; records every call it answers."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def generate(self, client: LLMClient, *, request: LLMRequestDTO) -> LLMResponseDTO:
        schema = (request.response_format or {}).get("json_schema", {}).get("name")
        self.calls.append(schema)

        if schema == "ExecutionPlanResponseSchema":
            content, usage = PLAN, PLANNER_USAGE
        else:
            content, usage = DECISION, AGENT_USAGE

        return LLMResponseDTO(
            content=json.dumps(content),
            provider=client.provider,
            model=client.model,
            usage=usage,
        )

    @property
    def expected(self) -> tuple[int, int]:
        """(input, output) tokens the calls answered so far add up to."""

        planner = self.calls.count("ExecutionPlanResponseSchema")
        agent = len(self.calls) - planner
        return (
            planner * PLANNER_USAGE.prompt_tokens + agent * AGENT_USAGE.prompt_tokens,
            planner * PLANNER_USAGE.completion_tokens + agent * AGENT_USAGE.completion_tokens,
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


async def _tokens_today(user_id: str) -> int:
    day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    async with session_factory() as session:
        return await UsageRecordRepository(session=session).get_daily_token_usage(
            user_id=user_id,
            window_start=day,
        )


@pytest.fixture(autouse=True)
def _rate_limit_on() -> None:
    assert get_settings().rate_limit.RATE_LIMIT_ENABLED, "these tests need RATE_LIMIT_ENABLED"


async def test_a_chat_turn_records_its_real_token_usage(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    provider: _Provider,
) -> None:
    response = await e2e_client.post(
        "/api/v1/chat",
        data={"conversation_id": conversation_id, "message": "What is an FIR?"},
        headers=registered_user["headers"],
    )

    assert response.status_code == 200, response.text
    # The planner and at least one agent call went through the real
    # LLMClient.generate().
    assert "ExecutionPlanResponseSchema" in provider.calls
    assert len(provider.calls) >= 2

    assert await _tokens_today(registered_user["user_id"]) == sum(provider.expected)


async def test_a_streamed_turn_records_the_same_way(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    provider: _Provider,
) -> None:
    async with e2e_client.stream(
        "POST",
        "/api/v1/chat/stream",
        data={"conversation_id": conversation_id, "message": "What is an FIR?"},
        headers=registered_user["headers"],
    ) as response:
        assert response.status_code == 200
        await response.aread()

    assert len(provider.calls) >= 2
    assert await _tokens_today(registered_user["user_id"]) == sum(provider.expected)


async def test_real_usage_exhausts_the_daily_quota(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    provider: _Provider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    With the quota set to one turn's usage, the turn itself is allowed
    (the check runs before it), and the next request is refused.
    """

    first = await e2e_client.post(
        "/api/v1/chat",
        data={"conversation_id": conversation_id, "message": "What is an FIR?"},
        headers=registered_user["headers"],
    )
    assert first.status_code == 200, first.text

    used = await _tokens_today(registered_user["user_id"])
    assert used > 0
    # The daily quota can't be below the per-request one, so lower that first.
    monkeypatch.setattr(get_settings().rate_limit, "TOKEN_QUOTA_PER_REQUEST", used)
    monkeypatch.setattr(get_settings().rate_limit, "TOKEN_QUOTA_DAILY", used)

    second = await e2e_client.post(
        "/api/v1/chat",
        data={"conversation_id": conversation_id, "message": "And a second question?"},
        headers=registered_user["headers"],
    )

    assert second.status_code == 429, second.text
    assert second.json()["error"]["code"] == ERROR_TOKEN_QUOTA_EXCEEDED
