"""
Shared setup for the HITL e2e tests (test_hitl_approval_flow.py,
test_hitl_decision_durability.py).

What's patched, and why -- each is an external or non-deterministic
boundary, not application logic:
  - LLMPlanGenerator.generate() / BaseAgent._reason(): the planner and
    agent LLM calls. A live model's tool choice isn't reproducible; these
    tests verify the HITL control plane, not reasoning quality.
  - AgentContinuationService._gate_final(): the answer-quality gate's
    judge call. Always accepts.
  - MCPServerRegistry.call_tool(): the outbound Gmail MCP hop. Every call
    is recorded, so a test can assert exactly what was sent, and how many
    times. Not patched for the live messaging suite (tests/e2e/
    live_messaging/), which sends for real.

RBAC is real (the default "member" role): the former "user-1" stub had
to be patched out for any of this to run.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import ExitStack, asynccontextmanager, contextmanager
from typing import Any
from unittest.mock import patch

from adapters.clients.mcp.registry import MCPServerRegistry
from adapters.persistence.sqlalchemy.repositories.agent_policy import (
    AgentPolicyRepository,
)
from adapters.persistence.sqlalchemy.session import session_factory
from agentic.agents.base import BaseAgent
from agentic.agents.runtime.continuation import AgentContinuationService
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision, AgentToolCall
from agentic.evaluation.answer import AnswerEvaluationSummary
from agentic.planning.llm_planner import LLMPlanGenerator
from core.dto.clients.mcp import MCPToolCallResult
from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from core.enums import AgentTypeEnum, ExecutionModeEnum, IntentEnum

# Classified SEND by the capability classifier, so the request-level RBAC
# check runs for real (it refused every real user before).
CHAT_MESSAGE = "Send the signature reminder for case 84021 to the client."

DRAFT = {
    "to": "client@example.org",
    "subject": "Case 84021: signature needed",
    "body": "Please sign the agreement at your earliest convenience.",
}

FINAL_ANSWER = "I've sent the client a reminder to sign the agreement for case 84021."

SENT_TEXT = "Message sent: id 42."

PENDING_APPROVAL_TEXT = "needs your approval"


def send_decision(parameters: dict[str, Any] | None = None) -> AgentDecision:
    return AgentDecision(
        decision_type=AgentDecisionType.TOOL_CALL,
        reason="The user asked to email the client.",
        tool_call=AgentToolCall(tool_name="email_send", parameters=parameters or dict(DRAFT)),
    )


def final_decision() -> AgentDecision:
    return AgentDecision(
        decision_type=AgentDecisionType.FINAL,
        reason="Email sent, answer ready.",
        final_response=FINAL_ANSWER,
    )


def approve_then_final_script() -> list[AgentDecision]:
    """
    The whole node (including the reasoning call) replays from the top on
    resume, so the SAME send decision comes back twice -- once before the
    pause, once during the replay -- then FINAL once the result is in.
    """

    return [send_decision(), send_decision(), final_decision()]


@asynccontextmanager
async def legal_agent_may_send(tool_name: str = "email_send") -> AsyncIterator[None]:
    """
    Temporarily grant the legal agent a send tool (email_send by default;
    no agent has one by default, ENABLE_MESSAGING_TOOLS grants them),
    restoring the policy after.
    """

    async with session_factory() as session:
        repository = AgentPolicyRepository(session=session)
        original = await repository.get_by_agent_id(agent_id="legal")
        original_tools = (
            list(original.allowed_tools) if original else ["retriever", "case_law_search"]
        )
        await repository.upsert(agent_id="legal", allowed_tools=[*original_tools, tool_name])
        await session.commit()

    try:
        yield
    finally:
        async with session_factory() as session:
            repository = AgentPolicyRepository(session=session)
            await repository.upsert(agent_id="legal", allowed_tools=original_tools)
            await session.commit()


@contextmanager
def scripted_boundaries(
    decisions: list[AgentDecision],
    mcp_calls: list[dict[str, Any]] | None,
) -> Iterator[None]:
    """
    Patch the LLM, judge and MCP boundaries. decisions is consumed in
    order; running out fails the test (an unexpected extra reasoning call,
    e.g. a resume that re-ran a finished turn). mcp_calls=None leaves the
    MCP hop real (the live messaging suite).
    """

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

    async def fake_reason(self, *, request, context=()):
        assert decisions, "BaseAgent._reason called more times than this test scripted."
        return decisions.pop(0)

    async def fake_plan_generate(self, *, request):
        return plan

    async def fake_gate_final(self, *, handle, result):
        return None, AnswerEvaluationSummary(groundedness=0.95, relevance=0.90)

    async def fake_call_tool(self, *, server_name, tool_name, arguments):
        assert mcp_calls is not None
        mcp_calls.append(
            {"server_name": server_name, "tool_name": tool_name, "arguments": arguments}
        )
        return MCPToolCallResult(
            tool_name=tool_name,
            server_name=server_name,
            is_error=False,
            content=[{"type": "text", "text": SENT_TEXT}],
        )

    with (
        patch.object(LLMPlanGenerator, "generate", fake_plan_generate),
        patch.object(BaseAgent, "_reason", fake_reason),
        patch.object(AgentContinuationService, "_gate_final", fake_gate_final),
        ExitStack() as mcp_patch,
    ):
        if mcp_calls is not None:
            mcp_patch.enter_context(patch.object(MCPServerRegistry, "call_tool", fake_call_tool))
        yield


async def start_pending_send(e2e_client, *, user: dict, conversation_id: str) -> dict:
    """
    Send the chat message and return the assistant event's pending
    approval, checking the pending-approval text (A6) on the way.
    """

    response = await e2e_client.post(
        "/api/v1/chat",
        data={"conversation_id": conversation_id, "message": CHAT_MESSAGE},
        headers=user["headers"],
    )
    assert response.status_code == 200, response.text

    assistant_event = response.json()["data"]["assistant_event"]
    assert PENDING_APPROVAL_TEXT in assistant_event["content"], assistant_event["content"]
    assert "went wrong" not in assistant_event["content"]

    return assistant_event["event_metadata"]["approval"]
