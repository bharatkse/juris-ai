"""
The agent's prompt lists exactly the tools its policy allows, with their
parameter schemas.

Before, no tool catalog reached the agent's LLM: the rendered prompt named
no tools, so every model-proposed TOOL_CALL was a guess at a name and its
parameters.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from agentic.agents.legal import LegalAgent
from agentic.agents.prompts.legal import LegalPromptBuilder
from agentic.agents.prompts.token_budget import DEFAULT_RESERVED_OUTPUT_TOKENS
from agentic.agents.prompts.tool_catalog import NO_TOOLS_MESSAGE, TOOL_CATALOG_HEADING
from agentic.agents.runtime.execution import AgentExecution
from agentic.agents.runtime.retry import RetryClassifier
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision, AgentToolCall
from agentic.decisions.validator import AgentDecisionValidator
from agentic.execution.config import ExecutionRetryPolicy
from agentic.policy.agent_policy import StaticAgentPolicyProvider
from agentic.policy.guard import AgentPolicyGuard
from agentic.policy.schemas import AgentPolicy
from agentic.policy.tool_permission import ToolPermissionGuard
from agentic.registry.agent import AgentRegistry
from agentic.registry.tool import ToolRegistry
from core.dto.agent import AgentContextDTO, AgentRequestDTO
from core.dto.conversation import ConversationDTO
from core.dto.message import MessageDTO
from core.enums import MessageRoleEnum
from wiring.containers import RegistryContainer
from wiring.factories.tools import register_tools

MODEL = "llama-3.3-70b-versatile"


def _request() -> AgentRequestDTO:
    return AgentRequestDTO(
        conversation=ConversationDTO(
            messages=(MessageDTO(role=MessageRoleEnum.USER, content="What is section 43?"),),
        ),
        instruction="Answer the user's legal question.",
        context=AgentContextDTO(
            user_id="u",
            execution_id="e",
            thread_id="t",
            conversation_event_id="c",
        ),
    )


def _execution(
    allowed_tools: frozenset[str],
    llm_client: AsyncMock | None = None,
) -> AgentExecution:
    agents = AgentRegistry()
    agents.register(component=LegalAgent(llm_client=llm_client or AsyncMock()))

    tools = ToolRegistry()
    register_tools(
        clients=MagicMock(),
        registries=RegistryContainer(agent_registry=agents, tool_registry=tools),
        approval_service=MagicMock(),
    )

    return AgentExecution(
        agent_registry=agents,
        retry_policy=ExecutionRetryPolicy(max_attempts=1),
        retry_classifier=RetryClassifier(),
        decision_validator=AgentDecisionValidator(),
        agent_policy_provider=StaticAgentPolicyProvider(
            policies={"legal": AgentPolicy(agent_id="legal", allowed_tools=allowed_tools)},
        ),
        agent_policy_guard=AgentPolicyGuard(tool_permission_guard=ToolPermissionGuard()),
        tool_registry=tools,
    )


def _tools_block(request: AgentRequestDTO) -> str:
    messages = (
        LegalPromptBuilder()
        .build(
            request=request,
            context=(),
            model=MODEL,
            reserved_output_tokens=DEFAULT_RESERVED_OUTPUT_TOKENS,
        )
        .messages
    )

    blocks = [m.content for m in messages if m.content.startswith(TOOL_CATALOG_HEADING)]
    assert len(blocks) == 1, "exactly one Available tools block"
    assert messages[1].content == blocks[0], "it follows the system prompt"
    assert messages[1].role is MessageRoleEnum.SYSTEM
    return blocks[0]


@pytest.mark.asyncio
async def test_prompt_lists_exactly_the_policy_allowed_tools_with_their_schemas() -> None:
    handle = await _execution(frozenset({"retriever", "case_law_search"})).start(
        agent_id="legal",
        request=_request(),
    )

    block = _tools_block(handle.request)

    listed = [line[5:-1] for line in block.splitlines() if line.startswith("### `")]
    assert listed == ["case_law_search", "retriever"]

    # Every registered tool the policy doesn't grant stays out.
    for name in ("web_research", "library_lookup", "parser", "email", "slack"):
        assert f"`{name}`" not in block

    # Each tool's schema is in the prompt, bounds included.
    retriever_schema = json.loads(
        block.split("### `retriever`", 1)[1]
        .split("Parameters (JSON Schema): ", 1)[1]
        .splitlines()[0]
    )
    assert retriever_schema["properties"]["top_k"]["maximum"] == 10
    assert retriever_schema["additionalProperties"] is False

    assert '"enum":["case_law","contracts"]' in block


@pytest.mark.asyncio
async def test_agent_with_no_callable_tools_is_told_not_to_call_any() -> None:
    # parser is granted but server-side only; nothing else is granted.
    handle = await _execution(frozenset({"parser"})).start(agent_id="legal", request=_request())

    assert handle.request.tool_catalog == ()
    assert _tools_block(handle.request) == f"{TOOL_CATALOG_HEADING}\n\n{NO_TOOLS_MESSAGE}"


@pytest.mark.asyncio
async def test_a_tool_call_using_a_catalog_name_passes_the_policy_check() -> None:
    """
    Every name the agent is shown is one its policy accepts: a TOOL_CALL
    that copies a catalog entry becomes an action, not FAILED_POLICY.
    """

    allowed = frozenset({"retriever", "case_law_search", "web_research"})
    llm_client = AsyncMock()
    execution = _execution(allowed, llm_client)
    catalog_names = [
        spec.name
        for spec in (
            await execution.start(agent_id="legal", request=_request())
        ).request.tool_catalog
    ]
    assert sorted(catalog_names) == sorted(allowed)

    for name in catalog_names:
        handle = await execution.start(agent_id="legal", request=_request())
        llm_client.generate_structured = AsyncMock(
            return_value=AgentDecision(
                decision_type=AgentDecisionType.TOOL_CALL,
                tool_call=AgentToolCall(tool_name=name, parameters={"query": "section 43"}),
            ),
        )

        result = await handle.reason()

        assert result.termination_reason is None, (name, result.error)
        assert result.action is not None
        assert result.action.tool_name == name


@pytest.mark.parametrize("template", ["legal.md", "contract.md"])
def test_agent_templates_point_tool_calls_at_the_catalog(template: str) -> None:
    from pathlib import Path

    import agentic.agents.prompts as prompts

    text = (Path(prompts.__file__).parent / "templates" / template).read_text()

    assert "Call only tools listed under **Available tools**" in text
    assert "must match that tool's JSON Schema under **Available tools**" in text
