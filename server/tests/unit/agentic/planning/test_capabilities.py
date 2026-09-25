"""
Unit tests for what the planner's LLM is told about agents and their tools.

The agents and tools come from the agent registry, the agent policies and
ToolRegistry.describe() (AgentCapabilityCatalog), never from planning.md, so
the planner can't offer a tool the runtime would refuse.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from agentic.agents.contract import ContractAgent
from agentic.agents.legal import LegalAgent
from agentic.planning.capabilities import AgentCapabilityCatalog
from agentic.planning.llm_planner import LLMPlanGenerator
from agentic.planning.prompts.agent_capabilities import (
    AGENT_CAPABILITIES_HEADING,
    render_agent_capabilities,
)
from agentic.planning.prompts.planning import PlanningPromptBuilder
from agentic.policy.agent_policy import StaticAgentPolicyProvider
from agentic.policy.schemas import AgentPolicy
from agentic.registry.agent import AgentRegistry
from agentic.registry.tool import ToolRegistry
from core.dto.planning import AgentCapabilityDTO, PlanningRequestDTO
from core.enums import AgentTypeEnum
from tests.builders.agentic.planning import build_execution_plan_response
from wiring.containers import RegistryContainer
from wiring.factories.agent_policies import _build_default_agent_policies
from wiring.factories.tools import register_tools


def _tool_registry() -> ToolRegistry:
    """Every tool production registers, with stubbed dependencies."""

    registry = ToolRegistry()
    register_tools(
        clients=MagicMock(),
        registries=RegistryContainer(agent_registry=AgentRegistry(), tool_registry=registry),
        approval_service=MagicMock(),
    )
    return registry


def _agent_registry(*agent_classes: type) -> AgentRegistry:
    registry = AgentRegistry()
    for agent_class in agent_classes:
        registry.register(component=agent_class(llm_client=MagicMock()))
    return registry


def _policies(**allowed_tools: set[str]) -> StaticAgentPolicyProvider:
    return StaticAgentPolicyProvider(
        policies={
            agent_id: AgentPolicy(agent_id=agent_id, allowed_tools=frozenset(tools))
            for agent_id, tools in allowed_tools.items()
        },
    )


def _catalog(
    policies: StaticAgentPolicyProvider,
    agents: AgentRegistry | None = None,
) -> AgentCapabilityCatalog:
    return AgentCapabilityCatalog(
        agent_registry=agents or _agent_registry(LegalAgent, ContractAgent),
        tool_registry=_tool_registry(),
        agent_policy_provider=policies,
    )


async def _planner_prompt(catalog: AgentCapabilityCatalog) -> str:
    """
    The whole prompt the planner's LLM receives, through the real
    LLMPlanGenerator and PlanningPromptBuilder (planning.md included).
    """

    llm_client = MagicMock()
    llm_client.generate_structured = AsyncMock(return_value=build_execution_plan_response())

    await LLMPlanGenerator(
        llm_client=llm_client,
        prompt_builder=PlanningPromptBuilder(),
        capability_catalog=catalog,
    ).generate(request=PlanningRequestDTO(message="Explain section 66 of the IT Act 2000."))

    request = llm_client.generate_structured.await_args.kwargs["request"]
    return "\n\n".join(message.content for message in request.messages)


def _agent_section(prompt: str, agent: str) -> str:
    """The prompt text between one agent's heading and the next heading."""

    start = prompt.index(f"### `{agent}`")
    end = prompt.find("\n### ", start + 1)
    return prompt[start : end if end != -1 else None]


# ----------------------------------------------------------------------
# AgentCapabilityCatalog
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_each_agent_is_described_with_exactly_the_tools_its_policy_allows() -> None:
    tools = _tool_registry()
    catalog = AgentCapabilityCatalog(
        agent_registry=_agent_registry(LegalAgent, ContractAgent),
        tool_registry=tools,
        agent_policy_provider=_policies(
            legal={"retriever", "case_law_search"},
            contract={"retriever", "library_lookup"},
        ),
    )

    capabilities = await catalog.describe()

    assert [capability.agent for capability in capabilities] == [
        AgentTypeEnum.LEGAL,
        AgentTypeEnum.CONTRACT,
    ]
    legal, contract = capabilities
    # The same ToolSpecDTOs the agent itself is given as its tool_catalog.
    assert legal.tools == tools.describe(names={"retriever", "case_law_search"})
    assert contract.tools == tools.describe(names={"retriever", "library_lookup"})
    assert legal.description == LegalAgent.metadata.description


@pytest.mark.asyncio
async def test_an_agent_with_no_policy_or_not_registered_is_left_out() -> None:
    no_contract_policy = _catalog(_policies(legal={"retriever"}))
    only_legal_registered = _catalog(
        _policies(legal={"retriever"}, contract={"retriever"}),
        agents=_agent_registry(LegalAgent),
    )

    for catalog in (no_contract_policy, only_legal_registered):
        assert [c.agent for c in await catalog.describe()] == [AgentTypeEnum.LEGAL]


@pytest.mark.asyncio
async def test_a_granted_tool_that_is_not_agent_callable_is_not_offered() -> None:
    # parser is server-side only; describe() drops it, as it does for the agent.
    (legal,) = await _catalog(_policies(legal={"retriever", "parser", "no_such_tool"})).describe()

    assert [tool.name for tool in legal.tools] == ["retriever"]


# ----------------------------------------------------------------------
# Drift: the planner's prompt follows the policies, not planning.md
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_policy_change_reaches_the_planner_prompt_without_editing_planning_md() -> None:
    before = await _planner_prompt(
        _catalog(_policies(legal={"retriever", "case_law_search"}, contract={"retriever"})),
    )
    after = await _planner_prompt(
        _catalog(_policies(legal={"retriever", "web_research"}, contract={"retriever", "email"})),
    )

    legal_before, legal_after = _agent_section(before, "legal"), _agent_section(after, "legal")
    assert "`case_law_search`" in legal_before and "`web_research`" not in legal_before
    assert "`web_research`" in legal_after and "`case_law_search`" not in legal_after

    contract_before = _agent_section(before, "contract")
    contract_after = _agent_section(after, "contract")
    assert "`email`" not in contract_before
    assert "`email`" in contract_after

    # Same template both times: only the generated block differs.
    template = PlanningPromptBuilder.load_template(PlanningPromptBuilder.template_name)
    assert before.startswith(template) and after.startswith(template)


def test_planning_md_names_no_agent_or_tool_itself() -> None:
    """
    The agent and tool list lives only in the generated block. A
    hand-written list in the template would drift from the policies.
    """

    template = PlanningPromptBuilder.load_template(PlanningPromptBuilder.template_name)

    assert AGENT_CAPABILITIES_HEADING not in template
    for agent in AgentTypeEnum:
        assert f"### {agent.value}\n" not in template
    for tool in _tool_registry().keys():
        assert f"`{tool}`" not in template
        assert f" {tool} " not in template


@pytest.mark.asyncio
async def test_with_the_default_policies_no_agent_is_offered_a_messaging_tool() -> None:
    prompt = await _planner_prompt(_catalog(_policies(**_build_default_agent_policies())))

    assert "`email`" not in prompt
    assert "`slack`" not in prompt
    assert "no other agents or tools exist" in prompt
    assert "`retriever`" in _agent_section(prompt, "legal")
    assert "`retriever`" in _agent_section(prompt, "contract")


# ----------------------------------------------------------------------
# render_agent_capabilities
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_block_names_tools_and_purposes_but_no_parameter_schemas() -> None:
    capabilities = await _catalog(_policies(legal={"retriever"})).describe()

    block = render_agent_capabilities(capabilities)

    (retriever,) = capabilities[0].tools
    assert f"- `retriever`: {retriever.description}" in block
    # Parameters are the agent's concern: its own prompt has the schemas.
    assert "top_k" not in block
    assert "Schema" not in block


def test_an_agent_with_no_tools_is_shown_as_having_none() -> None:
    block = render_agent_capabilities(
        (AgentCapabilityDTO(agent=AgentTypeEnum.LEGAL, description="Legal."),),
    )

    assert "### `legal`\nLegal.\nTools: none." in block


def test_no_capabilities_render_nothing() -> None:
    assert render_agent_capabilities(()) == ""
