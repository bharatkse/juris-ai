"""
E2E: when the groundedness judge's provider is down, the answer gate
returns the "couldn't verify" answer without retrying (review R17).

Over real HTTP and Postgres. Before, a judge outage cost a corrective
retrieval and a re-asked answer that the same judge then couldn't check
either. A judge verdict that is merely low (or unusable) is still retried,
and both end in the same answer to the user.

Only the LLM boundaries are stubbed: the planner, the agent's reasoning
call, and the groundedness judge (the hermetic_llm fixture); retrieval
returns one statute chunk (statute_evidence).
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from agentic.agents.base import BaseAgent
from agentic.agents.runtime.continuation import UNVERIFIED_ANSWER_MESSAGE
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision
from agentic.planning.llm_planner import LLMPlanGenerator
from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from core.enums import AgentTypeEnum, ExecutionModeEnum, IntentEnum

CHAT_MESSAGE = "What does section 2(1)(ta) of the IT Act 2000 define?"

# Echoes the question, so relevance (real local embeddings) passes and
# only groundedness decides.
FINAL_ANSWER = (
    "Section 2(1)(ta) of the IT Act 2000 defines 'electronic signature' "
    "as authentication of an electronic record by a subscriber using an "
    "electronic technique."
)


def _plan() -> ExecutionPlanDTO:
    return ExecutionPlanDTO(
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


async def _chat(e2e_client: AsyncClient, *, conversation_id: str, headers: dict) -> tuple:
    reasoning_calls = 0

    async def fake_reason(self, *, request, context=()):
        nonlocal reasoning_calls
        reasoning_calls += 1
        return AgentDecision(
            decision_type=AgentDecisionType.FINAL,
            reason="Answering.",
            final_response=FINAL_ANSWER,
        )

    async def fake_plan_generate(self, *, request):
        return _plan()

    async with AsyncExitStack() as patches:
        patches.enter_context(patch.object(LLMPlanGenerator, "generate", fake_plan_generate))
        patches.enter_context(patch.object(BaseAgent, "_reason", fake_reason))

        response = await e2e_client.post(
            "/api/v1/chat",
            data={"conversation_id": conversation_id, "message": CHAT_MESSAGE},
            headers=headers,
        )

    return response, reasoning_calls


@pytest.mark.asyncio
async def test_no_retry_when_the_judge_provider_is_down(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    statute_evidence: list[str],
    hermetic_llm,
) -> None:
    hermetic_llm.groundedness_provider_down = True

    response, reasoning_calls = await _chat(
        e2e_client, conversation_id=conversation_id, headers=registered_user["headers"]
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["response"]["content"] == UNVERIFIED_ANSWER_MESSAGE
    # One answer, judged once; only the seeding retrieval ran.
    assert reasoning_calls == 1
    assert hermetic_llm.groundedness_calls == 1
    assert len(statute_evidence) == 1


@pytest.mark.asyncio
async def test_a_low_score_is_still_retried_to_the_same_answer(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    statute_evidence: list[str],
    hermetic_llm,
) -> None:
    hermetic_llm.groundedness = 0.0

    response, reasoning_calls = await _chat(
        e2e_client, conversation_id=conversation_id, headers=registered_user["headers"]
    )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["response"]["content"] == UNVERIFIED_ANSWER_MESSAGE
    # Corrective retrieval and re-ask: more LLM calls for the same answer.
    assert reasoning_calls > 1
    assert hermetic_llm.groundedness_calls > 1
    assert len(statute_evidence) >= 2
