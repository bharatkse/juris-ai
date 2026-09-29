"""
E2E: a plan with more steps than one turn may run gets a normal reply
asking the user to split the request, and nothing is executed (review
A7). Before, any number of steps was accepted and run.

Requires the real Postgres/Redis services with migrations applied. Run via
`make test-e2e`.
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy import select

from adapters.clients.llm.base import LLMClient
from adapters.persistence.sqlalchemy.models.conversation_event import ConversationEvent
from adapters.persistence.sqlalchemy.session import session_factory
from agentic.planning.llm_planner import LLMPlanGenerator
from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from core.enums import AgentTypeEnum, ExecutionModeEnum, IntentEnum, MessageRoleEnum

MESSAGE = "Compare notice periods across every act in the corpus, one by one."


def _chain(length: int) -> ExecutionPlanDTO:
    return ExecutionPlanDTO(
        intent=IntentEnum.GENERAL,
        mode=ExecutionModeEnum.SEQUENTIAL,
        steps=tuple(
            ExecutionStepDTO(
                id=f"step-{index}",
                agent=AgentTypeEnum.LEGAL,
                instruction=f"Part {index}.",
                depends_on=(f"step-{index - 1}",) if index else (),
                stage=index + 1,
                arguments={},
            )
            for index in range(length)
        ),
        metadata={},
    )


async def test_a_plan_over_the_step_limit_is_answered_not_run(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
) -> None:
    agent_calls: list[object] = []

    async def fake_plan_generate(self, *, request):
        return _chain(7)

    async def fake_generate_structured(self, *, request, response_model):
        agent_calls.append(request)
        raise AssertionError("no agent should run for a refused plan")

    async with AsyncExitStack() as patches:
        patches.enter_context(patch.object(LLMPlanGenerator, "generate", fake_plan_generate))
        patches.enter_context(
            patch.object(LLMClient, "generate_structured", fake_generate_structured)
        )

        response = await e2e_client.post(
            "/api/v1/chat",
            data={"conversation_id": conversation_id, "message": MESSAGE},
            headers=registered_user["headers"],
        )

    assert response.status_code == 200, response.text
    content = response.json()["data"]["response"]["content"]
    assert content == (
        "This request would need 7 steps, but I can run at most 6 in one turn. "
        "Please split it into smaller questions."
    )
    assert agent_calls == []

    # The reply is persisted as the conversation's assistant message, like
    # any answer.
    async with session_factory() as session:
        persisted = await session.scalars(
            select(ConversationEvent.content).where(
                ConversationEvent.conversation_id == conversation_id,
                ConversationEvent.role == MessageRoleEnum.ASSISTANT,
            )
        )
        assert list(persisted) == [content]
