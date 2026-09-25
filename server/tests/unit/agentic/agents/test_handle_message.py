"""
Unit tests for the tools an agent is told about when it handles an
agent-to-agent collaboration message (BaseAgent.handle_message()).

Delegation is unreachable in production today
(AgentPolicyGuard.check_delegation() always denies), so these tests send
the message through the real CollaborationBus directly, as
AgentContinuationService._delegate() would once delegation is allowed.
The parent's request comes from the real AgentExecution.start(), so it
carries the parent's own tool catalog, as it would in production.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from adapters.clients.llm.base import LLMClient
from agentic.agents.contract import ContractAgent
from agentic.agents.legal import LegalAgent
from agentic.agents.prompts.tool_catalog import NO_TOOLS_MESSAGE, TOOL_CATALOG_HEADING
from agentic.agents.runtime.execution import AgentExecution
from agentic.agents.runtime.retry import RetryClassifier
from agentic.collaboration.bus import CollaborationBus
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision
from agentic.decisions.validator import AgentDecisionValidator
from agentic.execution.config import ExecutionRetryPolicy
from agentic.policy.agent_policy import StaticAgentPolicyProvider
from agentic.policy.guard import AgentPolicyGuard
from agentic.policy.schemas import AgentPolicy
from agentic.policy.tool_catalog import AgentToolCatalog
from agentic.policy.tool_permission import ToolPermissionGuard
from agentic.registry.agent import AgentRegistry
from agentic.registry.tool import ToolRegistry
from config.settings import get_settings
from core.dto.agent import AgentContextDTO, AgentRequestDTO
from core.dto.conversation import ConversationDTO
from core.dto.message import MessageDTO
from core.enums import MessageRoleEnum
from core.models.message import AgentMessageSchema
from wiring.containers import RegistryContainer
from wiring.factories.tools import register_tools

LEGAL_TOOLS = frozenset({"retriever", "case_law_search"})
CONTRACT_TOOLS = frozenset({"retriever", "library_lookup"})


def _tool_registry() -> ToolRegistry:
    """Every tool production registers, with stubbed dependencies."""

    registry = ToolRegistry()
    register_tools(
        clients=MagicMock(),
        registries=RegistryContainer(agent_registry=AgentRegistry(), tool_registry=registry),
        approval_service=MagicMock(),
    )
    return registry


def _llm_client() -> MagicMock:
    client = MagicMock(spec=LLMClient)
    client.model = get_settings().llm.GROQ_MODEL
    client.generate_structured = AsyncMock(
        return_value=AgentDecision(decision_type=AgentDecisionType.FINAL, final_response="Done."),
    )
    return client


class _Setup:
    """Legal (parent) and contract (target) agents with different tools."""

    def __init__(self, *, target_catalog: bool = True) -> None:
        self.tools = _tool_registry()
        self.policies = StaticAgentPolicyProvider(
            policies={
                "legal": AgentPolicy(agent_id="legal", allowed_tools=LEGAL_TOOLS),
                "contract": AgentPolicy(agent_id="contract", allowed_tools=CONTRACT_TOOLS),
            },
        )
        catalog = AgentToolCatalog(agent_policy_provider=self.policies, tool_registry=self.tools)

        self.legal_llm, self.contract_llm = _llm_client(), _llm_client()
        self.agents = AgentRegistry()
        self.agents.register(component=LegalAgent(llm_client=self.legal_llm, tool_catalog=catalog))
        self.contract = ContractAgent(
            llm_client=self.contract_llm,
            tool_catalog=catalog if target_catalog else None,
        )
        self.agents.register(component=self.contract)

        self.bus = CollaborationBus()
        self.bus.register(agent="contract", handler=self.contract)

        self.execution = AgentExecution(
            agent_registry=self.agents,
            retry_policy=ExecutionRetryPolicy(),
            retry_classifier=RetryClassifier(),
            decision_validator=AgentDecisionValidator(),
            agent_policy_provider=self.policies,
            agent_policy_guard=AgentPolicyGuard(tool_permission_guard=ToolPermissionGuard()),
            tool_registry=self.tools,
        )

    async def request_for(self, agent_id: str) -> AgentRequestDTO:
        """The request AgentExecution.start() builds for this agent."""

        handle = await self.execution.start(
            agent_id=agent_id,
            request=AgentRequestDTO(
                conversation=ConversationDTO(
                    messages=(MessageDTO(role=MessageRoleEnum.USER, content="Review clause 7."),),
                ),
                instruction="Review the termination clause.",
                arguments={},
                context=AgentContextDTO(
                    user_id="u", execution_id="e", thread_id="t", conversation_event_id="c"
                ),
            ),
        )
        return handle.request

    async def delegate_to_contract(self, parent_request: AgentRequestDTO) -> object:
        return await self.bus.send(
            message=AgentMessageSchema(
                sender="legal",
                recipient="contract",
                capability=AgentDecisionType.DELEGATE.value,
                payload={"request": parent_request, "parameters": {"clause": "7"}},
            ),
        )


def _tools_block(llm: MagicMock) -> str:
    request = llm.generate_structured.await_args.kwargs["request"]
    (block,) = (m.content for m in request.messages if m.content.startswith(TOOL_CATALOG_HEADING))
    return block


@pytest.mark.asyncio
async def test_a_delegated_agent_is_told_its_own_tools_not_the_parents_or_none() -> None:
    setup = _Setup()
    parent_request = await setup.request_for("legal")
    assert {spec.name for spec in parent_request.tool_catalog} == LEGAL_TOOLS

    decision = await setup.delegate_to_contract(parent_request)

    assert isinstance(decision, AgentDecision)
    block = _tools_block(setup.contract_llm)
    assert "### `library_lookup`" in block
    assert "### `retriever`" in block
    assert "### `case_law_search`" not in block  # the parent's tool
    assert NO_TOOLS_MESSAGE not in block
    setup.legal_llm.generate_structured.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_delegated_catalog_matches_what_normal_execution_gives_the_target() -> None:
    setup = _Setup()

    await setup.delegate_to_contract(await setup.request_for("legal"))

    delegated = setup.contract_llm.generate_structured.await_args.kwargs["request"]
    normal = (await setup.request_for("contract")).tool_catalog
    assert _tools_block(setup.contract_llm) in {m.content for m in delegated.messages}
    assert [spec.name for spec in normal] == ["library_lookup", "retriever"]
    for spec in normal:
        assert f"### `{spec.name}`\n{spec.description}" in _tools_block(setup.contract_llm)


@pytest.mark.asyncio
async def test_the_delegated_request_keeps_the_parents_task_and_adds_the_parameters() -> None:
    setup = _Setup()
    setup.contract._reason = AsyncMock(  # type: ignore[method-assign]
        return_value=AgentDecision(decision_type=AgentDecisionType.FINAL, final_response="Done."),
    )

    await setup.delegate_to_contract(await setup.request_for("legal"))

    delegated = setup.contract._reason.await_args.kwargs["request"]
    assert delegated.instruction == "Review the termination clause."
    assert delegated.arguments == {"clause": "7"}
    assert {spec.name for spec in delegated.tool_catalog} == CONTRACT_TOOLS


@pytest.mark.asyncio
async def test_without_a_tool_catalog_the_agent_refuses_rather_than_offer_no_tools() -> None:
    setup = _Setup(target_catalog=False)

    with pytest.raises(RuntimeError, match="no tool catalog"):
        await setup.delegate_to_contract(await setup.request_for("legal"))

    setup.contract_llm.generate_structured.assert_not_awaited()
