"""
E2E: when the harmful-content judge can't be reached, the answer is
withheld and the client gets the fixed refusal (fail closed, A8).

Over real HTTP, real Postgres/Redis, the real orchestrator and the real
OutputGuardrailService / HarmfulContentJudge. Only the judge's LLM call is
replaced, by one that raises -- what a bad API key, rate limit or outage
looks like from the judge's side. (This is the
situation that made other e2e tests "refuse" correct answers when they
still reached Groq for real; conftest.py's hermetic_llm fixture now
stubs the judge for them, and this test keeps the failure path covered
on purpose.)

What's mocked besides that: the planner and the agent's reasoning, as in
test_agent_decision_compliance_log.py, so the agent deterministically
produces an ordinary, harmless answer.
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from agentic.agents.base import BaseAgent
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision
from agentic.orchestration.orchestrator import _GUARDRAIL_BLOCKED_MESSAGE
from agentic.planning.llm_planner import LLMPlanGenerator
from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from core.enums import AgentTypeEnum, ExecutionModeEnum, IntentEnum
from tests.e2e.conftest import LLMStub

CHAT_MESSAGE = "What does section 2(1)(ta) of the IT Act 2000 define?"
FINAL_ANSWER = (
    "Section 2(1)(ta) of the IT Act 2000 defines 'electronic signature' "
    "as authentication of an electronic record by a subscriber using an "
    "electronic technique."
)


class ProviderUnavailable(RuntimeError):
    """Stands in for a provider error (401, 429, timeout...)."""


@pytest.fixture
def unavailable_judge(hermetic_llm: LLMStub) -> LLMStub:
    # Must be set before e2e_client starts the app, which is when the
    # guardrail service (and its judge) is built -- hence a fixture
    # listed ahead of e2e_client rather than a patch in the test body.
    hermetic_llm.judge_error = ProviderUnavailable("401 Unauthorized")
    return hermetic_llm


@pytest.mark.asyncio
async def test_unreachable_judge_withholds_the_answer(
    unavailable_judge: LLMStub,
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
) -> None:
    plan = ExecutionPlanDTO(
        intent=IntentEnum.GENERAL,
        mode=ExecutionModeEnum.SEQUENTIAL,
        steps=(
            ExecutionStepDTO(
                id="step-1",
                agent=AgentTypeEnum.LEGAL,
                instruction=CHAT_MESSAGE,
                depends_on=(),
                stage=1,
                arguments={},
            ),
        ),
        metadata={},
    )

    async def fake_plan_generate(self, *, request):
        return plan

    async def fake_reason(self, *, request, context=()):
        return AgentDecision(
            decision_type=AgentDecisionType.FINAL,
            reason="Answering directly from known statute text.",
            final_response=FINAL_ANSWER,
        )

    async with AsyncExitStack() as patches:
        patches.enter_context(patch.object(LLMPlanGenerator, "generate", fake_plan_generate))
        patches.enter_context(patch.object(BaseAgent, "_reason", fake_reason))

        response = await e2e_client.post(
            "/api/v1/chat",
            data={"conversation_id": conversation_id, "message": CHAT_MESSAGE},
            headers=registered_user["headers"],
        )

    # The request itself succeeds -- a judge outage isn't a server error.
    assert response.status_code == 200, response.text
    content = response.json()["data"]["response"]["content"]

    # ...but the unreviewed answer never reaches the client.
    assert content == _GUARDRAIL_BLOCKED_MESSAGE
    assert FINAL_ANSWER not in response.text

    # The judge was genuinely attempted rather than skipped.
    assert unavailable_judge.judge_calls >= 1
