"""
E2E: a chat request's token usage is recorded exactly once, whether the
request succeeds, fails partway, is refused by the request token quota,
or is cancelled by a client disconnecting from /chat/stream (review R19).

Before the fix only a returned response's usage (and the quota refusal's)
was recorded: tokens spent by a request that raised or was cancelled never
reached the daily quota.

Each request leaves one usage_request_records row (unique request_id) with
the tokens its LLM calls used; the day bucket in usage_records grows by the
same amount. Provider calls are stubbed at each client's _generate(), as in
test_token_usage.py, so the real LLMClient.generate() counts them.

Requires the real Postgres/Redis services with migrations applied. Run via
`make test-e2e`.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from adapters.clients.llm.base import LLMClient
from adapters.clients.llm.groq import GroqClient
from adapters.clients.llm.local import LocalLLMClient
from adapters.persistence.sqlalchemy.models.usage_request_record import UsageRequestRecord
from adapters.persistence.sqlalchemy.repositories.usage_record import UsageRecordRepository
from adapters.persistence.sqlalchemy.session import session_factory
from agentic.guardrails.service import OutputGuardrailService
from config.settings import get_settings
from core.dto.clients.llm import LLMRequestDTO, LLMResponseDTO, LLMTokenUsageDTO

# Captured at import, before the hermetic_llm fixture replaces it.
REAL_GENERATE = LLMClient.generate

PLANNER = "ExecutionPlanResponseSchema"
PLANNER_USAGE = LLMTokenUsageDTO(prompt_tokens=1000, completion_tokens=200, total_tokens=1200)
AGENT_USAGE = LLMTokenUsageDTO(prompt_tokens=700, completion_tokens=100, total_tokens=800)
MESSAGE = "What is an FIR?"

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
    """Stands in for Groq and Ollama. hold_agent parks the agent's call."""

    def __init__(self) -> None:
        self.calls: list[str | None] = []
        self.hold_agent: asyncio.Event | None = None
        self.agent_waiting = asyncio.Event()
        self.planner_usage = PLANNER_USAGE

    async def generate(self, client: LLMClient, *, request: LLMRequestDTO) -> LLMResponseDTO:
        schema = (request.response_format or {}).get("json_schema", {}).get("name")

        if schema != PLANNER and self.hold_agent is not None:
            self.agent_waiting.set()
            await self.hold_agent.wait()

        self.calls.append(schema)
        content, usage = (
            (PLAN, self.planner_usage) if schema == PLANNER else (DECISION, AGENT_USAGE)
        )

        return LLMResponseDTO(
            content=json.dumps(content),
            provider=client.provider,
            model=client.model,
            usage=usage,
        )

    @property
    def expected(self) -> tuple[int, int]:
        planner = self.calls.count(PLANNER)
        agent = len(self.calls) - planner
        return (
            planner * self.planner_usage.prompt_tokens + agent * AGENT_USAGE.prompt_tokens,
            planner * self.planner_usage.completion_tokens + agent * AGENT_USAGE.completion_tokens,
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
def _rate_limit_on() -> None:
    assert get_settings().rate_limit.RATE_LIMIT_ENABLED, "these tests need RATE_LIMIT_ENABLED"


async def _records(user_id: str) -> list[UsageRequestRecord]:
    async with session_factory() as session:
        result = await session.execute(
            select(UsageRequestRecord).where(UsageRequestRecord.user_id == user_id)
        )
        return list(result.scalars().all())


async def _tokens_today(user_id: str) -> int:
    day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    async with session_factory() as session:
        return await UsageRecordRepository(session=session).get_daily_token_usage(
            user_id=user_id, window_start=day
        )


async def _one_record(user_id: str, expected: tuple[int, int]) -> None:
    records = await _records(user_id)
    assert len(records) == 1, records
    assert (records[0].input_tokens, records[0].output_tokens) == expected
    assert await _tokens_today(user_id) == sum(expected)


async def test_a_successful_request_is_recorded_once(
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
    assert PLANNER in provider.calls and len(provider.calls) >= 2
    await _one_record(registered_user["user_id"], provider.expected)


async def test_a_request_failing_after_its_llm_calls_is_recorded(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    provider: _Provider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The planner and the agent ran, then the output review raised."""

    async def failing_review(self, *args, **kwargs):
        raise RuntimeError("guardrail review failed")

    monkeypatch.setattr(OutputGuardrailService, "review", failing_review)

    # Unhandled, so the test client re-raises it (a 500 to a real client).
    with pytest.raises(RuntimeError, match="guardrail review failed"):
        await e2e_client.post(
            "/api/v1/chat",
            data={"conversation_id": conversation_id, "message": MESSAGE},
            headers=registered_user["headers"],
        )

    assert PLANNER in provider.calls and len(provider.calls) >= 2
    await _one_record(registered_user["user_id"], provider.expected)


async def test_a_quota_refusal_is_recorded_once(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    provider: _Provider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unchanged behaviour (413, the planner's tokens counted), now one ledger row."""

    monkeypatch.setattr(get_settings().rate_limit, "TOKEN_QUOTA_PER_REQUEST", 50_000)
    # The planner's call leaves 10 tokens, so the agent's call is refused.
    provider.planner_usage = LLMTokenUsageDTO(
        prompt_tokens=49_000, completion_tokens=990, total_tokens=49_990
    )

    response = await e2e_client.post(
        "/api/v1/chat",
        data={"conversation_id": conversation_id, "message": MESSAGE},
        headers=registered_user["headers"],
    )

    assert response.status_code == 413, response.text
    assert provider.calls == [PLANNER]
    await _one_record(registered_user["user_id"], provider.expected)


async def test_a_stream_the_client_abandons_is_recorded(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    provider: _Provider,
) -> None:
    """
    The client goes away while the agent's call is in flight: the request
    is cancelled; the planner's tokens were spent and are recorded.
    """

    provider.hold_agent = asyncio.Event()

    async def consume() -> None:
        async with e2e_client.stream(
            "POST",
            "/api/v1/chat/stream",
            data={"conversation_id": conversation_id, "message": MESSAGE},
            headers=registered_user["headers"],
        ) as response:
            await response.aread()

    client = asyncio.create_task(consume())
    await asyncio.wait_for(provider.agent_waiting.wait(), timeout=10)
    client.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await client

    assert provider.calls == [PLANNER]

    # The write is shielded from the cancellation and finishes on its own.
    for _ in range(50):
        if await _records(registered_user["user_id"]):
            break
        await asyncio.sleep(0.1)

    await _one_record(registered_user["user_id"], provider.expected)


async def test_recording_the_same_request_twice_counts_it_once(
    registered_user: dict,
) -> None:
    """The ledger's unique request_id makes record() idempotent."""

    from uuid import uuid4

    from application.services.usage import UsageService

    user_id = registered_user["user_id"]
    request_id = str(uuid4())

    async with session_factory() as session:
        service = UsageService(
            session=session,
            repository=UsageRecordRepository(session=session),
            record_session_factory=session_factory,
        )
        for _ in range(2):
            await service.record(
                user_id=user_id, request_id=request_id, input_tokens=120, output_tokens=30
            )

    await _one_record(user_id, (120, 30))
