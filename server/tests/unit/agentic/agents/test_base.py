from unittest.mock import AsyncMock, MagicMock

import pytest

from agentic.agents.base import BaseAgent
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision, AgentToolCall
from tests.builders.adapters.clients.llm import build_llm_request


class TestAgent(BaseAgent):
    """
    Minimal agent implementation for BaseAgent tests.
    """

    metadata = ...


@pytest.fixture
def llm_client() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def prompt_builder() -> MagicMock:
    """
    BasePromptBuilder.build() is synchronous in BaseAgent.

    Use MagicMock here so build() returns the provider-independent request
    immediately instead of returning a coroutine.
    """
    builder = MagicMock()
    builder.build.return_value = build_llm_request()
    return builder


@pytest.fixture
def agent(
    llm_client: AsyncMock,
    prompt_builder: MagicMock,
) -> TestAgent:
    return TestAgent(
        llm_client=llm_client,
        prompt_builder=prompt_builder,
    )


@pytest.fixture
def mock_request():
    return ...


@pytest.mark.asyncio
async def test_reason_returns_agent_decision(
    agent: TestAgent,
    llm_client: AsyncMock,
    mock_request,
) -> None:
    decision = AgentDecision(
        decision_type=AgentDecisionType.FINAL,
        final_response="The contract requires 30 days' notice.",
    )

    llm_client.generate_structured.return_value = decision

    result = await agent._reason(
        request=mock_request,
    )

    assert result == decision

    llm_client.generate_structured.assert_awaited_once()

    call = llm_client.generate_structured.await_args

    assert call.kwargs["response_model"] is AgentDecision


@pytest.mark.asyncio
async def test_reason_supports_tool_call_decision(
    agent: TestAgent,
    llm_client: AsyncMock,
    mock_request,
) -> None:
    decision = AgentDecision(
        decision_type=AgentDecisionType.TOOL_CALL,
        reason="Additional contract evidence is required.",
        tool_call=AgentToolCall(
            tool_name="retriever",
            parameters={
                "query": "termination clause",
            },
        ),
    )

    llm_client.generate_structured.return_value = decision

    result = await agent._reason(
        request=mock_request,
    )

    assert result.decision_type is AgentDecisionType.TOOL_CALL
    assert result.tool_call is not None
    assert result.tool_call.tool_name == "retriever"

    call = llm_client.generate_structured.await_args

    assert call.kwargs["response_model"] is AgentDecision
