"""
E2E: the original DuplicateAgentResponseError production repro,
driven through the real planner -> validator -> executor path, over
real HTTP, real Postgres, the real LangGraph checkpointer, and the
real ExecutionPlanValidator -- not the validator's own unit tests
(tests/unit/agentic/planning/test_validator.py), which exercise
_validate_agent_concurrency directly. This is the verification vehicle
for the fix: a plan with two independent (no depends_on) steps both
assigned to the same agent must be rejected at planning time, before
any agent is invoked -- not accepted, executed, and only caught
afterward by ResponseValidator once both agent calls have already run.

Same pattern as tests/e2e/test_user_memory_chat_wiring.py: real
FastAPI routing/middleware/DI, JWT auth, Postgres, the real
orchestrator/executor/validator stack; only the LLM-reasoning boundary
is scripted.

What's real: AIOrchestrator.handle() -> ExecutionPlanner.create_plan()
-> ExecutionPlanValidator.validate() (this is the exact call path the
production bug went through) -> (on the pre-fix behavior) Executor ->
AgentExecutionNode -> BaseAgent._reason().

What's mocked, and why -- the same LLM-reasoning boundary
test_user_memory_chat_wiring.py mocks, nothing more:
  - LLMPlanGenerator.generate(): scripted to return the exact plan
    shape that reproduced the production bug (two steps, both agent
    'legal', neither depends_on the other) -- standing in for "the
    planner LLM happened to produce this shape", which is the
    precondition the fix must guard against regardless of why the LLM
    produced it.
  - BaseAgent._reason(): scripted to record whether it was ever
    called. It must NOT be called at all once the fix is in place --
    that is the whole point of catching this at planning time rather
    than at post-execution response validation.

Requires the real Postgres/Redis docker compose services running
(`./setup.sh --install --dependency postgres --dependency redis`).
Run via `make test-e2e`.
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from agentic.agents.base import BaseAgent
from agentic.planning.llm_planner import LLMPlanGenerator
from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from core.enums import AgentTypeEnum, ExecutionModeEnum, IntentEnum


def _duplicate_agent_independent_steps_plan() -> ExecutionPlanDTO:
    """
    The exact plan shape that reproduced the production
    DuplicateAgentResponseError: two steps, both assigned to the
    'legal' agent, neither depending on the other -- so the executor
    is free to run them concurrently (see
    ExecutionGraphBuilder._add_edges, which derives topology purely
    from depends_on).
    """

    return ExecutionPlanDTO(
        intent=IntentEnum.GENERAL,
        mode=ExecutionModeEnum.PARALLEL,
        steps=(
            ExecutionStepDTO(
                id="step-1",
                agent=AgentTypeEnum.LEGAL,
                instruction="Answer the first part of the question.",
                depends_on=(),
                stage=1,
                arguments={},
            ),
            ExecutionStepDTO(
                id="step-2",
                agent=AgentTypeEnum.LEGAL,
                instruction="Answer the second part of the question.",
                depends_on=(),
                stage=1,
                arguments={},
            ),
        ),
        metadata={},
    )


@pytest.mark.asyncio
async def test_duplicate_agent_on_independent_steps_is_rejected_at_planning_time(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
) -> None:
    """
    The real production repro: reject the bad plan shape at
    ExecutionPlanValidator, before any agent LLM call runs, instead of
    letting both agent calls execute and failing later with
    DuplicateAgentResponseError.
    """

    reason_called = False

    async def fake_plan_generate(self, *, request):
        return _duplicate_agent_independent_steps_plan()

    async def fake_reason(self, *, request, context=()):
        nonlocal reason_called
        reason_called = True

        raise AssertionError(
            "BaseAgent._reason() was called -- the invalid plan reached "
            "agent execution instead of being rejected at planning time."
        )

    async with AsyncExitStack() as patches:
        patches.enter_context(patch.object(LLMPlanGenerator, "generate", fake_plan_generate))
        patches.enter_context(patch.object(BaseAgent, "_reason", fake_reason))

        response = await e2e_client.post(
            "/api/v1/chat",
            data={
                "conversation_id": conversation_id,
                "message": "Answer this in two independent parts.",
            },
            headers=registered_user["headers"],
        )

    # Rejected at planning time: PlanValidationError (AIError base,
    # HTTP 500) via the app's generic AppError handler
    # (api/exception_handlers.py) -- not a 200, and not the 422
    # DUPLICATE_AGENT_RESPONSE this same plan shape used to produce
    # only after both agent calls had already run.
    assert response.status_code == 500, response.text

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "PLAN_VALIDATION_ERROR"
    assert "no dependency relationship" in body["error"]["message"]

    # The cheaper, more important assertion: no agent LLM call ever
    # happened. Pre-fix, this plan shape reached BaseAgent._reason()
    # twice (once per step) before ResponseValidator caught the
    # duplicate -- two wasted real LLM calls. Post-fix, zero.
    assert reason_called is False
