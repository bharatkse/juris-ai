"""
E2E: a planner call that hangs (a stalled local model) ends the request with
504 PLANNING_TIMEOUT within the planner timeout, instead of holding it open
(review R18). Nothing is planned or run; the USER message is rolled back like
any failed request's.

The planner's model call is stubbed one level down (LocalLLMClient._generate)
so the real LLMClient.generate() and the real LLMPlanGenerator run; the
timeout is shortened on the running app's planner.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from httpx import AsyncClient

from adapters.clients.llm.base import LLMClient
from adapters.clients.llm.local import LocalLLMClient
from core.constants import ERROR_PLANNING_TIMEOUT
from main import app as fastapi_app

REAL_GENERATE = LLMClient.generate
TIMEOUT = 0.5


@pytest.fixture
def hung_planner(e2e_client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    async def hang(self, *, request):
        await asyncio.Event().wait()

    monkeypatch.setattr(LLMClient, "generate", REAL_GENERATE)
    monkeypatch.setattr(LocalLLMClient, "_generate", hang)
    llm_planner = fastapi_app.state.ai_orchestrator._planner._llm_planner
    monkeypatch.setattr(llm_planner, "_timeout_seconds", TIMEOUT)


async def test_a_hung_planner_times_out_with_a_clean_error(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    hung_planner: None,
) -> None:
    started = time.monotonic()
    response = await e2e_client.post(
        "/api/v1/chat",
        # No template matches this, so the LLM planner runs.
        data={"conversation_id": conversation_id, "message": "Summarise my situation."},
        headers=registered_user["headers"],
    )

    assert time.monotonic() - started < TIMEOUT + 5
    assert response.status_code == 504, response.text
    assert response.json()["error"]["code"] == ERROR_PLANNING_TIMEOUT


async def test_a_hung_planner_ends_a_stream_with_an_error_event(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    hung_planner: None,
) -> None:
    async with e2e_client.stream(
        "POST",
        "/api/v1/chat/stream",
        data={"conversation_id": conversation_id, "message": "Summarise my situation."},
        headers=registered_user["headers"],
    ) as response:
        body = (await response.aread()).decode()

    assert "event: error" in body
    assert ERROR_PLANNING_TIMEOUT in body
