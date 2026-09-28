"""
Unit tests for a delegated agent's turn (DelegatedAgentRunner).

Delegation is disabled in production (no agent policy allows it), so these
tests give the delegating agent a test policy that does, and drive the
real path: the parent's AgentContinuationService, the real
AgentPolicyGuard.check_delegation(), the real CollaborationBus, the
runner, and the target's AgentExecution + continuation with a real
ToolRegistry and ToolExecutionService. Only the two agents' LLM calls and
the answer-quality evaluation are stubbed.
"""

from __future__ import annotations

from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import Field

from adapters.clients.llm.base import LLMClient
from agentic.agents.contract import ContractAgent
from agentic.agents.legal import LegalAgent
from agentic.agents.prompts.tool_catalog import TOOL_CATALOG_HEADING
from agentic.agents.runtime.continuation import AgentContinuationService
from agentic.agents.runtime.delegation import DelegatedAgentRunner
from agentic.agents.runtime.execution import AgentExecution
from agentic.agents.runtime.feedback import is_feedback
from agentic.agents.runtime.retry import RetryClassifier
from agentic.collaboration.bus import CollaborationBus
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision, AgentDelegation, AgentToolCall
from agentic.decisions.validator import AgentDecisionValidator
from agentic.execution.config import ExecutionRetryPolicy
from agentic.policy.agent_policy import StaticAgentPolicyProvider
from agentic.policy.guard import AgentPolicyGuard
from agentic.policy.schemas import AgentPolicy
from agentic.policy.tool_permission import ToolPermissionGuard
from agentic.registry.agent import AgentRegistry
from agentic.registry.tool import ToolRegistry
from agentic.tools.base import Tool, ToolParams
from agentic.tools.runtime.invocation import ToolExecutionService
from config.settings import get_settings
from core.dto.agent import AgentContextDTO, AgentRequestDTO
from core.dto.conversation import ConversationDTO
from core.dto.message import MessageDTO
from core.enums import ExecutionStatusEnum, MessageRoleEnum

CLAUSE_TEXT = "Clause 7: either party may terminate on 30 days' notice."
CHILD_ANSWER = "Under clause 7, either party may terminate on 30 days' notice."
PARENT_ANSWER = "The lease can be ended on 30 days' notice (clause 7)."


class ClauseLookupParams(ToolParams):
    query: str = Field(min_length=1)


class ClauseLookupTool(Tool):
    """A contract tool only the target agent may use."""

    name = "clause_lookup"
    description = "Look up a clause in the uploaded contract."
    params_model: ClassVar[type[ToolParams] | None] = ClauseLookupParams

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def execute(self, *, query: str) -> str:
        self.calls.append({"query": query})
        return CLAUSE_TEXT


class CaseSearchTool(Tool):
    """A tool only the delegating agent may use."""

    name = "case_search"
    description = "Search case law."
    params_model: ClassVar[type[ToolParams] | None] = ClauseLookupParams

    async def execute(self, *, query: str) -> str:
        raise AssertionError("the delegating agent's tool must not run")


def _llm(*decisions: AgentDecision) -> MagicMock:
    client = MagicMock(spec=LLMClient)
    client.model = get_settings().llm.GROQ_MODEL
    client.generate_structured = AsyncMock(side_effect=list(decisions))
    return client


def _final(text: str) -> AgentDecision:
    return AgentDecision(decision_type=AgentDecisionType.FINAL, final_response=text)


def _clause_call(**parameters: object) -> AgentDecision:
    return AgentDecision(
        decision_type=AgentDecisionType.TOOL_CALL,
        tool_call=AgentToolCall(tool_name="clause_lookup", parameters=parameters),
    )


DELEGATE = AgentDecision(
    decision_type=AgentDecisionType.DELEGATE,
    delegation=AgentDelegation(target_agent_id="contract", parameters={"clause": "7"}),
)


def _prompts(llm: MagicMock) -> list[str]:
    """Every prompt this LLM received, messages joined."""

    return [
        "\n\n".join(message.content for message in call.kwargs["request"].messages)
        for call in llm.generate_structured.await_args_list
    ]


class _Runtime:
    """Two agents, their policies and tools, wired like production."""

    def __init__(self, *, legal: MagicMock, contract: MagicMock) -> None:
        self.clause_lookup = ClauseLookupTool()
        tools = ToolRegistry()
        tools.register(component=self.clause_lookup)
        tools.register(component=CaseSearchTool())

        agents = AgentRegistry()
        agents.register(component=LegalAgent(llm_client=legal))
        agents.register(component=ContractAgent(llm_client=contract))

        policies = StaticAgentPolicyProvider(
            policies={
                # Only the test policy allows delegation; production has none.
                "legal": AgentPolicy(
                    agent_id="legal",
                    allowed_tools=frozenset({"case_search"}),
                    allowed_agents=frozenset({"contract"}),
                    allow_delegation=True,
                ),
                "contract": AgentPolicy(
                    agent_id="contract",
                    allowed_tools=frozenset({"clause_lookup"}),
                ),
            },
        )
        guard = AgentPolicyGuard(tool_permission_guard=ToolPermissionGuard())

        self.execution = AgentExecution(
            agent_registry=agents,
            retry_policy=ExecutionRetryPolicy(max_attempts=1),
            retry_classifier=RetryClassifier(),
            decision_validator=AgentDecisionValidator(),
            agent_policy_provider=policies,
            agent_policy_guard=guard,
            tool_registry=tools,
        )

        quality_policy = MagicMock()
        quality_policy.is_sufficient.return_value = True
        self.evaluator = AsyncMock()

        bus = CollaborationBus()
        self.continuation = AgentContinuationService(
            tool_execution_service=ToolExecutionService(tool_registry=tools),
            collaboration_bus=bus,
            answer_evaluator=self.evaluator,
            answer_quality_policy=quality_policy,
            agent_policy_guard=guard,
            compliance_log=AsyncMock(),
        )
        for agent_id in agents.keys():
            bus.register(
                agent=agent_id,
                handler=DelegatedAgentRunner(
                    agent_id=agent_id,
                    agent_execution=self.execution,
                    continuation_service=self.continuation,
                ),
            )

    async def run_legal(self):
        handle = await self.execution.start(
            agent_id="legal",
            request=AgentRequestDTO(
                conversation=ConversationDTO(
                    messages=(
                        MessageDTO(
                            role=MessageRoleEnum.USER,
                            content="How much notice does the lease need to terminate?",
                        ),
                    ),
                ),
                instruction="Answer the user's question about the lease.",
                arguments={},
                context=AgentContextDTO(
                    user_id="u", execution_id="e", thread_id="t", conversation_event_id="c"
                ),
            ),
        )
        result = await self.continuation.execute(
            handle=handle,
            initial_result=await handle.reason(),
        )
        return handle, result


@pytest.mark.asyncio
async def test_a_delegated_tool_call_runs_the_tool_and_its_result_reaches_the_answer() -> None:
    legal = _llm(DELEGATE, _final(PARENT_ANSWER))
    contract = _llm(_clause_call(query="termination notice"), _final(CHILD_ANSWER))
    runtime = _Runtime(legal=legal, contract=contract)

    handle, result = await runtime.run_legal()

    # The target's TOOL_CALL ran the real tool, through ToolExecutionService.
    assert runtime.clause_lookup.calls == [{"query": "termination notice"}]

    # The tool's output reached the target's next reasoning call...
    contract_prompts = _prompts(contract)
    assert CLAUSE_TEXT not in contract_prompts[0]
    assert CLAUSE_TEXT in contract_prompts[1]

    # ...and the target's final answer, not its decision object, reached
    # the delegating agent.
    (delegated,) = (
        item
        for item in handle.reasoning_context
        if item.metadata.get("source_type") == "agent_delegation"
    )
    assert delegated.content == CHILD_ANSWER
    assert CHILD_ANSWER in _prompts(legal)[1]
    # No stringified decision (pydantic repr), and the target's tool name
    # and raw tool output stay inside the target's own turn.
    for fragment in ("decision_type=", "clause_lookup", CLAUSE_TEXT):
        assert fragment not in _prompts(legal)[1]

    assert result.result.status is ExecutionStatusEnum.COMPLETED
    assert result.result.decision.final_response == PARENT_ANSWER


@pytest.mark.asyncio
async def test_the_delegated_agent_is_told_its_own_tools_not_the_delegating_agents() -> None:
    legal = _llm(DELEGATE, _final(PARENT_ANSWER))
    contract = _llm(_final(CHILD_ANSWER))
    runtime = _Runtime(legal=legal, contract=contract)

    await runtime.run_legal()

    (tools_block,) = (
        m.content
        for m in contract.generate_structured.await_args.kwargs["request"].messages
        if m.content.startswith(TOOL_CATALOG_HEADING)
    )
    assert "### `clause_lookup`" in tools_block
    assert "### `case_search`" not in tools_block


@pytest.mark.asyncio
async def test_a_rejected_delegated_tool_call_is_fed_back_and_retried() -> None:
    legal = _llm(DELEGATE, _final(PARENT_ANSWER))
    contract = _llm(
        _clause_call(query="termination notice", not_a_param=1),
        _clause_call(query="termination notice"),
        _final(CHILD_ANSWER),
    )
    runtime = _Runtime(legal=legal, contract=contract)

    handle, _ = await runtime.run_legal()

    # The invalid call never reached the tool; its sanitized error did
    # reach the model, which corrected the call.
    assert runtime.clause_lookup.calls == [{"query": "termination notice"}]
    assert "Your call to tool 'clause_lookup' failed" in _prompts(contract)[1]
    assert "not_a_param" in _prompts(contract)[1]
    assert CHILD_ANSWER in [item.content for item in handle.reasoning_context]


@pytest.mark.asyncio
async def test_a_delegated_turn_without_a_verified_answer_reaches_the_parent_as_a_note() -> None:
    legal = _llm(DELEGATE, _final(PARENT_ANSWER))
    # The target keeps proposing a tool its policy doesn't allow, until its
    # rejected-decision budget runs out: no answer.
    denied = AgentDecision(
        decision_type=AgentDecisionType.TOOL_CALL,
        tool_call=AgentToolCall(tool_name="case_search", parameters={"query": "x"}),
    )
    contract = _llm(denied, denied, denied, denied)
    runtime = _Runtime(legal=legal, contract=contract)

    handle, _ = await runtime.run_legal()

    delegation_items = [
        item
        for item in handle.reasoning_context
        if item.metadata.get("source_type") == "agent_delegation"
    ]
    assert delegation_items == []
    (note,) = (
        item
        for item in handle.reasoning_context
        if is_feedback(item) and "Agent 'contract'" in item.content
    )
    assert "could not produce a verified answer" in note.content
    assert "case_search" not in note.content
