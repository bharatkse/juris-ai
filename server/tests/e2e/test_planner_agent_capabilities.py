"""
E2E: the planner is told each agent's tools as the agent_policies table
grants them.

Before, the planner's agent list was hand-written prose in planning.md,
disconnected from the policies the runtime enforces, so it could plan
steps no agent was allowed to carry out.

What's real: HTTP, JWT auth, Postgres (the agent_policies row this test
changes), the startup policy seeding, the planner's AgentCapabilityCatalog
and prompt builder, the execution graph, the answer-quality gate.

What's mocked: LLMClient.generate_structured() -- the planner's call
(recorded, answered with a fixed one-step plan) and the agent's call (a
FINAL answer). Retrieval finds nothing (empty_corpus); the answer content
isn't what this test checks.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

from adapters.clients.llm.base import LLMClient
from adapters.persistence.sqlalchemy.repositories.agent_policy import AgentPolicyRepository
from adapters.persistence.sqlalchemy.session import session_factory
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision
from core.enums import AgentTypeEnum, ExecutionModeEnum, IntentEnum
from core.models.planning import ExecutionPlanResponseSchema, ExecutionStepResponseSchema

QUESTION = "What does section 66 of the IT Act 2000 say about computer related offences?"


@pytest_asyncio.fixture
async def legal_policy(e2e_client: AsyncClient) -> AsyncIterator[list[str]]:
    """
    The legal agent's seeded policy, restored after the test. Applied
    after the app's lifespan has seeded the defaults (via e2e_client).
    """

    async with session_factory() as session:
        original = await AgentPolicyRepository(session=session).get_by_agent_id(agent_id="legal")
    assert original is not None
    original_tools = list(original.allowed_tools)

    try:
        yield original_tools
    finally:
        await _set_legal_tools(original_tools)


async def _set_legal_tools(tools: list[str]) -> None:
    async with session_factory() as session:
        await AgentPolicyRepository(session=session).upsert(agent_id="legal", allowed_tools=tools)
        await session.commit()


async def _planner_prompt(e2e_client, registered_user, conversation_id) -> str:
    planner_prompts: list[str] = []

    async def fake_generate_structured(self, *, request, response_model):
        if response_model is ExecutionPlanResponseSchema:
            planner_prompts.append("\n\n".join(m.content for m in request.messages))
            return ExecutionPlanResponseSchema(
                intent=IntentEnum.LEGAL_RESEARCH,
                mode=ExecutionModeEnum.SEQUENTIAL,
                steps=(
                    ExecutionStepResponseSchema(
                        id="step-1", agent=AgentTypeEnum.LEGAL, instruction=QUESTION
                    ),
                ),
            )
        return AgentDecision(decision_type=AgentDecisionType.FINAL, final_response="Answer.")

    with patch.object(LLMClient, "generate_structured", fake_generate_structured):
        response = await e2e_client.post(
            "/api/v1/chat",
            data={"conversation_id": conversation_id, "message": QUESTION},
            headers=registered_user["headers"],
        )

    assert response.status_code == 200, response.text
    (prompt,) = planner_prompts
    return prompt


def _agent_section(prompt: str, agent: str) -> str:
    start = prompt.index(f"### `{agent}`")
    end = prompt.find("\n### ", start + 1)
    return prompt[start : end if end != -1 else None]


@pytest.mark.asyncio
async def test_the_planner_prompt_follows_the_agent_policy_table(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    legal_policy: list[str],
    empty_corpus: list[str],
    hermetic_llm,
) -> None:
    # As seeded: every tool the policy grants is listed for legal; email isn't.
    seeded = _agent_section(
        await _planner_prompt(e2e_client, registered_user, conversation_id), "legal"
    )
    for tool in legal_policy:
        assert f"`{tool}`" in seeded
    assert "`email`" not in seeded

    # Change the row: the next plan sees it, with no code or template change.
    await _set_legal_tools(["retriever", "email"])

    changed = _agent_section(
        await _planner_prompt(e2e_client, registered_user, conversation_id), "legal"
    )
    assert "`email`" in changed
    assert "`retriever`" in changed
    assert "`case_law_search`" not in changed
