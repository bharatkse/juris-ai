"""
E2E: the planner's local-model call is bounded, and fails over to Groq
(review R18).

- Failover off: a hung local model ends the request with 504
  PLANNING_TIMEOUT within the planner timeout, instead of holding it open.
  Nothing is planned or run; the USER message is rolled back like any failed
  request's. A local model that errors is 503 PLANNING_UNAVAILABLE.
- Failover on: a local model that is down has the plan made by Groq; one
  that hangs, with Groq hanging too, still ends in 504 within the request's
  deadline; and with too little of the deadline left, Groq isn't called.
  Both providers failing with an error (no timeout) is 503
  PLANNING_UNAVAILABLE, with a Retry-After header.

The model calls are stubbed one level down (LocalLLMClient._generate,
GroqClient._generate) so the real LLMClient.generate() and the real
LLMPlanGenerator run; timeouts are shortened on the running app.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from httpx import AsyncClient

from adapters.clients.llm.base import LLMClient
from adapters.clients.llm.groq import GroqClient
from adapters.clients.llm.local import LocalLLMClient
from agentic.agents.base import BaseAgent
from core.constants import ERROR_PLANNING_TIMEOUT, ERROR_PLANNING_UNAVAILABLE
from core.dto.clients.llm import LLMResponseDTO
from core.enums import AgentTypeEnum, ExecutionModeEnum, IntentEnum
from core.exceptions.client import ClientConnectionError
from core.models.planning import ExecutionPlanResponseSchema, ExecutionStepResponseSchema
from main import app as fastapi_app
from tests.e2e.hitl_helpers import final_decision

REAL_GENERATE = LLMClient.generate
TIMEOUT = 0.5
# No template matches this, so the LLM planner runs.
MESSAGE = "Summarise my situation."


async def _hang(self, *, request):
    await asyncio.Event().wait()


def _llm_planner():
    return fastapi_app.state.ai_orchestrator._planner._llm_planner


@pytest.fixture
def hung_planner(e2e_client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A hung local model, with failover off."""

    monkeypatch.setattr(LLMClient, "generate", REAL_GENERATE)
    monkeypatch.setattr(LocalLLMClient, "_generate", _hang)
    monkeypatch.setattr(_llm_planner(), "_timeout_seconds", TIMEOUT)
    monkeypatch.setattr(_llm_planner(), "_fallback_llm", None)


@pytest.fixture
def groq_calls(e2e_client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """
    Failover on (the app's default wiring). The real client calls run down
    to the provider hop; each test decides what the providers do. Returns
    the prompts Groq received.
    """

    assert _llm_planner()._fallback_llm is not None, "failover should be on by default"
    monkeypatch.setattr(LLMClient, "generate", REAL_GENERATE)
    monkeypatch.setattr(_llm_planner(), "_timeout_seconds", TIMEOUT)
    return []


def _plan_json() -> str:
    return ExecutionPlanResponseSchema(
        intent=IntentEnum.GENERAL,
        mode=ExecutionModeEnum.SEQUENTIAL,
        steps=(
            ExecutionStepResponseSchema(
                id="step-1",
                agent=AgentTypeEnum.LEGAL,
                instruction=MESSAGE,
                depends_on=(),
                stage=1,
                arguments={},
            ),
        ),
        metadata={},
    ).model_dump_json()


async def test_a_hung_planner_times_out_with_a_clean_error(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    hung_planner: None,
) -> None:
    started = time.monotonic()
    response = await e2e_client.post(
        "/api/v1/chat",
        data={"conversation_id": conversation_id, "message": MESSAGE},
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
        data={"conversation_id": conversation_id, "message": MESSAGE},
        headers=registered_user["headers"],
    ) as response:
        body = (await response.aread()).decode()

    assert "event: error" in body
    assert ERROR_PLANNING_TIMEOUT in body


async def test_without_failover_a_local_error_is_planning_unavailable(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def local_down(self, *, request):
        raise ClientConnectionError()

    monkeypatch.setattr(LLMClient, "generate", REAL_GENERATE)
    monkeypatch.setattr(LocalLLMClient, "_generate", local_down)
    monkeypatch.setattr(_llm_planner(), "_fallback_llm", None)

    response = await e2e_client.post(
        "/api/v1/chat",
        data={"conversation_id": conversation_id, "message": MESSAGE},
        headers=registered_user["headers"],
    )

    assert response.status_code == 503, response.text
    assert response.json()["error"]["code"] == ERROR_PLANNING_UNAVAILABLE
    assert response.json()["error"]["details"] == {"retry_after_seconds": 30}
    assert response.headers["retry-after"] == "30"


async def test_a_local_model_that_is_down_has_its_plan_made_by_groq(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    groq_calls: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def local_down(self, *, request):
        raise ClientConnectionError()

    async def groq_plans(self, *, request):
        groq_calls.append(request.messages[-1].content)
        if "ExecutionPlanResponseSchema" not in str(request.response_format):
            raise ClientConnectionError()  # only the planner is expected here
        return LLMResponseDTO(content=_plan_json(), provider="groq", model="stub")

    async def reason(self, *, request, context=()):
        return final_decision()

    monkeypatch.setattr(LocalLLMClient, "_generate", local_down)
    monkeypatch.setattr(GroqClient, "_generate", groq_plans)
    monkeypatch.setattr(BaseAgent, "_reason", reason)

    response = await e2e_client.post(
        "/api/v1/chat",
        data={"conversation_id": conversation_id, "message": MESSAGE},
        headers=registered_user["headers"],
    )

    assert response.status_code == 200, response.text
    assert len(groq_calls) == 1


async def test_both_providers_hanging_ends_in_a_planning_timeout(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    groq_calls: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def groq_hangs(self, *, request):
        groq_calls.append(request.messages[-1].content)
        await asyncio.Event().wait()

    monkeypatch.setattr(LocalLLMClient, "_generate", _hang)
    monkeypatch.setattr(GroqClient, "_generate", groq_hangs)
    # The failover gets what is left of the request's deadline.
    monkeypatch.setattr(fastapi_app.state.ai_orchestrator, "_request_timeout_seconds", 6.0)

    started = time.monotonic()
    response = await e2e_client.post(
        "/api/v1/chat",
        data={"conversation_id": conversation_id, "message": MESSAGE},
        headers=registered_user["headers"],
    )

    assert time.monotonic() - started < 6.0 + 5
    assert response.status_code == 504, response.text
    assert response.json()["error"]["code"] == ERROR_PLANNING_TIMEOUT
    assert len(groq_calls) == 1


async def test_with_no_time_left_groq_is_not_called(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    groq_calls: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def groq_plans(self, *, request):
        groq_calls.append(request.messages[-1].content)
        return LLMResponseDTO(content=_plan_json(), provider="groq", model="stub")

    monkeypatch.setattr(LocalLLMClient, "_generate", _hang)
    monkeypatch.setattr(GroqClient, "_generate", groq_plans)
    # Less than the planner's minimum failover time is left once the
    # local call times out.
    monkeypatch.setattr(fastapi_app.state.ai_orchestrator, "_request_timeout_seconds", TIMEOUT + 1)

    response = await e2e_client.post(
        "/api/v1/chat",
        data={"conversation_id": conversation_id, "message": MESSAGE},
        headers=registered_user["headers"],
    )

    assert response.status_code == 504, response.text
    assert groq_calls == []


@pytest.fixture
def both_providers_down(groq_calls: list[str], monkeypatch: pytest.MonkeyPatch) -> list[str]:
    async def down(self, *, request):
        if isinstance(self, GroqClient):
            groq_calls.append(request.messages[-1].content)
        raise ClientConnectionError()

    monkeypatch.setattr(LocalLLMClient, "_generate", down)
    monkeypatch.setattr(GroqClient, "_generate", down)
    return groq_calls


async def test_both_providers_erroring_is_planning_unavailable(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    both_providers_down: list[str],
) -> None:
    response = await e2e_client.post(
        "/api/v1/chat",
        data={"conversation_id": conversation_id, "message": MESSAGE},
        headers=registered_user["headers"],
    )

    assert response.status_code == 503, response.text
    error = response.json()["error"]
    assert error["code"] == ERROR_PLANNING_UNAVAILABLE
    assert error["details"] == {"retry_after_seconds": 30}
    assert response.headers["retry-after"] == "30"
    assert len(both_providers_down) == 1


async def test_both_providers_erroring_ends_a_stream_with_an_error_event(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    both_providers_down: list[str],
) -> None:
    async with e2e_client.stream(
        "POST",
        "/api/v1/chat/stream",
        data={"conversation_id": conversation_id, "message": MESSAGE},
        headers=registered_user["headers"],
    ) as response:
        body = (await response.aread()).decode()

    assert "event: error" in body
    assert ERROR_PLANNING_UNAVAILABLE in body
    # No headers mid-stream: the event carries when to retry.
    assert '"retry_after_seconds":30' in body.replace(" ", "")
