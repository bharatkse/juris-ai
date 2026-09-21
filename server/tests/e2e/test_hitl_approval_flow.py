"""
E2E: full HITL approve flow, over real HTTP, real Postgres, real Redis.

auth -> chat (triggers a gated "email" TOOL_CALL) -> pending-approval
response -> POST /approvals/{id} (APPROVE) -> the tool actually runs
-> the conversation shows the completed outcome.

What's real: FastAPI routing/middleware/dependency-injection, JWT
auth, Postgres (users, conversations, agent_policies, agent_actions,
approvals, usage_records), the real Postgres-backed LangGraph
checkpointer, the real execution graph, ToolExecutionService,
ApprovalLifecyclePolicy, ApprovalLifecycleService, HitlResumeService,
and the real EmailTool (its own read()/execute()/_call_mcp() code all
runs for real).

What's mocked, and why -- each is an external or non-deterministic
boundary this test has no business depending on, not application
logic:
  - LLMPlanGenerator.generate() / BaseAgent._reason(): the two real
    LLM calls (agentic/CLAUDE.md's "two separate LLM calls" -- planner
    and agent). A live model's tool-choice on a free-text prompt isn't
    reliably reproducible turn to turn, and this test's job is to
    verify the HITL control plane, not agent reasoning quality.
  - AgentContinuationService._gate_final(): the answer-quality gate
    calls a real Groq-backed FaithfulnessBackend (see
    agentic/evaluation/answer.py) -- another live LLM call, orthogonal
    to what this test verifies. Patched to always accept the FINAL
    answer as-is.
  - MCPServerRegistry.call_tool(): the actual outbound Gmail MCP
    network call EmailTool.read() makes. No Gmail MCP server exists in
    this test environment; this is the one genuinely external network
    edge the whole flow reaches.
  - RBACService.check_action(): application/authorization/rbac/policy.py's
    RBACPolicy.default() is a hardcoded stub keyed on the literal
    user_id "user-1" -- no real registered user can ever pass it (a
    real, pre-existing gap this test surfaced, not something this
    session introduced or is scoped to fix). Patched to always allow,
    since real RBAC coverage is its own separate concern from the HITL
    flow this test verifies.

Everything these mocks stand in for is deliberately still exercised
for real up to that exact boundary -- e.g. EmailTool.execute() really
runs and really calls _call_mcp(), only the network hop underneath it
is faked.

Requires the real Postgres/Redis docker compose services running
(`./setup.sh --install --dependency postgres
--dependency redis`). Run via `make test-e2e`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

from adapters.clients.mcp.registry import MCPServerRegistry
from adapters.persistence.sqlalchemy.repositories.agent_policy import (
    AgentPolicyRepository,
)
from adapters.persistence.sqlalchemy.repositories.conversation_event import (
    ConversationEventRepository,
)
from adapters.persistence.sqlalchemy.session import session_factory
from agentic.agents.base import BaseAgent
from agentic.agents.runtime.continuation import AgentContinuationService
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision, AgentToolCall
from agentic.evaluation.answer import AnswerEvaluationSummary
from agentic.planning.llm_planner import LLMPlanGenerator
from application.authorization.rbac.resolver import RBACService
from application.services.conversation_event import ConversationEventService
from core.dto.clients.mcp import MCPToolCallResult
from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from core.enums import AgentTypeEnum, ApprovalStatusEnum, ExecutionModeEnum, IntentEnum

# tests/conftest.py's pytest_collection_modifyitems auto-tags every
# test under tests/e2e/ with the "e2e" marker — no pytestmark needed
# here, matching the existing unit/smoke convention.

CHAT_MESSAGE = "Check my email for updates on case 84021 and let me know."
FINAL_ANSWER = (
    "I checked your email and found one update on case 84021: the "
    "client still needs to sign. I've flagged it for follow-up."
)
FAKE_EMAIL_MCP_TEXT = "Found 1 message: Re: Case 84021 - awaiting client signature."


@pytest_asyncio.fixture
async def legal_agent_email_policy() -> AsyncIterator[None]:
    """
    Temporarily grant the "legal" agent the "email" tool.

    No seeded agent is granted email/slack by default (deliberately --
    see wiring/factories/agent_policies.py); this test needs it to
    reach the gated-tool path at all. Applied AFTER the app's lifespan
    has already run seed_default_agent_policies() (that only happens
    once, at startup, via the e2e_client fixture) and restored
    afterward so this test doesn't leave a permanent policy change
    behind in a real, shared database.
    """

    async with session_factory() as session:
        repository = AgentPolicyRepository(session=session)
        original = await repository.get_by_agent_id(agent_id="legal")
        original_tools = (
            list(original.allowed_tools) if original else ["retriever", "case_law_search"]
        )

        await repository.upsert(
            agent_id="legal",
            allowed_tools=[*original_tools, "email"],
        )
        await session.commit()

    try:
        yield
    finally:
        async with session_factory() as session:
            repository = AgentPolicyRepository(session=session)
            await repository.upsert(agent_id="legal", allowed_tools=original_tools)
            await session.commit()


@pytest.mark.asyncio
async def test_hitl_approve_flow_executes_gated_tool_exactly_once(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    legal_agent_email_policy: None,
) -> None:
    # ------------------------------------------------------------
    # Scripted decisions for the real continuation loop's real
    # while-loop. The whole node (including this call) replays from
    # the top on resume (see continuation.py's _execute_gated_tool()
    # docstring), so the SAME TOOL_CALL(email) decision must come back
    # twice: once before the pause, once during the replay after
    # resume -- then a fresh FINAL once the tool result is in context.
    # ------------------------------------------------------------
    tool_call_decision = AgentDecision(
        decision_type=AgentDecisionType.TOOL_CALL,
        reason="Need to check email for case updates before answering.",
        tool_call=AgentToolCall(
            tool_name="email",
            parameters={"query": "case 84021", "limit": 5},
        ),
    )
    final_decision = AgentDecision(
        decision_type=AgentDecisionType.FINAL,
        reason="Email checked, answer ready.",
        final_response=FINAL_ANSWER,
    )
    decisions = [tool_call_decision, tool_call_decision, final_decision]

    async def fake_reason(self, *, request, context=()):
        assert decisions, "BaseAgent._reason called more times than this test scripted."
        return decisions.pop(0)

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

    async def fake_gate_final(self, *, handle, result):
        # Answer-quality gating is out of scope for this test -- always
        # accept the FINAL result as-is (see module docstring). Returns
        # the same (accepted_result, evaluation_summary) shape the real
        # _gate_final does on its accept path -- deterministic stand-in
        # scores, not a real judge call, but real enough to verify the
        # compliance log's AGENT_DECISION row actually receives them
        # (see application/services/compliance_log.py).
        return None, AnswerEvaluationSummary(groundedness=0.95, relevance=0.90)

    mcp_calls: list[dict] = []

    async def fake_call_tool(self, *, server_name, tool_name, arguments):
        mcp_calls.append(
            {"server_name": server_name, "tool_name": tool_name, "arguments": arguments}
        )
        return MCPToolCallResult(
            tool_name=tool_name,
            server_name=server_name,
            is_error=False,
            content=[{"type": "text", "text": FAKE_EMAIL_MCP_TEXT}],
        )

    async with AsyncExitStack() as patches:
        patches.enter_context(patch.object(LLMPlanGenerator, "generate", fake_plan_generate))
        patches.enter_context(patch.object(BaseAgent, "_reason", fake_reason))
        patches.enter_context(
            patch.object(AgentContinuationService, "_gate_final", fake_gate_final)
        )
        patches.enter_context(patch.object(MCPServerRegistry, "call_tool", fake_call_tool))
        patches.enter_context(patch.object(RBACService, "check_action", lambda self, request: True))

        # --------------------------------------------------------
        # 1. Send the chat message that triggers the gated TOOL_CALL.
        # --------------------------------------------------------
        chat_response = await e2e_client.post(
            "/api/v1/chat",
            data={"conversation_id": conversation_id, "message": CHAT_MESSAGE},
            headers=registered_user["headers"],
        )
        assert chat_response.status_code == 200, chat_response.text
        chat_body = chat_response.json()["data"]

        # ConversationEventResponse's `metadata` field serializes under
        # its DB-column alias, "event_metadata" -- confirmed against
        # the real wire response, not assumed.
        assistant_metadata = chat_body["assistant_event"]["event_metadata"]
        assert "approval" in assistant_metadata, (
            f"Expected a pending approval in the assistant event metadata, "
            f"got: {assistant_metadata}"
        )
        approval_info = assistant_metadata["approval"]
        assert approval_info["status"] == ApprovalStatusEnum.WAITING.value
        approval_id = approval_info["approval_id"]

        # The tool must NOT have run yet -- only a real human decision
        # executes a gated tool.
        assert mcp_calls == []

        # --------------------------------------------------------
        # 2. Approve the pending action.
        # --------------------------------------------------------
        approve_response = await e2e_client.post(
            f"/api/v1/approvals/{approval_id}",
            json={"decision": "approve"},
            headers=registered_user["headers"],
        )
        assert approve_response.status_code == 200, approve_response.text
        approve_body = approve_response.json()["data"]
        assert approve_body["status"] == ApprovalStatusEnum.APPROVED.value
        assert approve_body["approval_id"] == approval_id

    # --------------------------------------------------------
    # 3. The gated tool actually executed -- exactly once, not zero,
    #    not twice, despite the replayed reasoning call above.
    # --------------------------------------------------------
    assert len(mcp_calls) == 1, f"Expected exactly one real MCP call, got: {mcp_calls}"
    assert mcp_calls[0]["server_name"] == "gmail"
    assert mcp_calls[0]["tool_name"] == "search_messages"

    # --------------------------------------------------------
    # 4. The conversation shows the completed outcome. There is no
    #    "get conversation events" HTTP endpoint yet (see
    #    api/v1/endpoints/conversations.py), so this reads the
    #    persisted result directly -- the same real Postgres row the
    #    API itself just wrote via HitlResumeService.
    # --------------------------------------------------------
    async with session_factory() as session:
        events = await ConversationEventService(
            session=session,
            repository=ConversationEventRepository(session=session),
        ).list(conversation_id=conversation_id, limit=20)

    resumed_events = [
        event for event in events if (event.event_metadata or {}).get("resumed_agent_action_id")
    ]
    assert len(resumed_events) == 1, (
        f"Expected exactly one resumed-turn assistant event, found "
        f"{len(resumed_events)} among {len(events)} total events."
    )
    assert resumed_events[0].content == FINAL_ANSWER
