from unittest.mock import AsyncMock, MagicMock

import pytest

from agentic.agents.base import BaseAgent
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision, AgentToolCall
from core.dto.clients.llm import LLMStreamChunkDTO
from core.dto.tool import RetrievedContentDTO
from core.enums import RetrievalSourceEnum
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


@pytest.mark.asyncio
async def test_stream_final_answer_passes_the_given_context_to_the_prompt_builder(
    agent: TestAgent,
    llm_client: AsyncMock,
    prompt_builder: MagicMock,
    mock_request,
) -> None:
    """
    Regression test for the fix to the now-deleted stream(): that
    method hardcoded context=() when building the prompt (confirmed
    unreachable in production, and worthless even if it had been
    reached). stream_final_answer() must actually forward whatever
    accumulated reasoning_context its caller supplies -- the real fix
    that makes this not worthless once wired up (Phase 3).
    """

    context = (
        RetrievedContentDTO(
            source=RetrievalSourceEnum.VECTOR,
            source_name="it-act-2000",
            content="Section 43A: compensation for failure to protect data.",
        ),
    )

    async def fake_stream(**_kwargs):
        yield LLMStreamChunkDTO(content="The contract", is_final=False)
        yield LLMStreamChunkDTO(content=" requires notice.", is_final=True, finish_reason="stop")

    llm_client.stream = MagicMock(side_effect=fake_stream)

    chunks = [
        chunk
        async for chunk in agent.stream_final_answer(
            request=mock_request,
            context=context,
        )
    ]

    prompt_builder.build.assert_called_once()
    assert prompt_builder.build.call_args.kwargs["context"] == context

    assert [chunk.content for chunk in chunks] == [
        "The contract",
        " requires notice.",
    ]
    assert [chunk.is_final for chunk in chunks] == [False, True]
    assert chunks[-1].finish_reason == "stop"


@pytest.mark.asyncio
async def test_stream_final_answer_defaults_to_empty_context(
    agent: TestAgent,
    llm_client: AsyncMock,
    prompt_builder: MagicMock,
    mock_request,
) -> None:
    """
    context is optional -- a caller with nothing accumulated yet
    (e.g. a FINAL decision reached with no TOOL_CALL ever made) must
    not be forced to pass an empty tuple explicitly.
    """

    async def fake_stream(**_kwargs):
        yield LLMStreamChunkDTO(content="Answer.", is_final=True, finish_reason="stop")

    llm_client.stream = MagicMock(side_effect=fake_stream)

    async for _ in agent.stream_final_answer(request=mock_request):
        pass

    assert prompt_builder.build.call_args.kwargs["context"] == ()


@pytest.mark.asyncio
async def test_stream_final_answer_uses_freeform_not_structured_output(
    agent: TestAgent,
    llm_client: AsyncMock,
    prompt_builder: MagicMock,
    mock_request,
) -> None:
    """
    The whole reason this method exists separately from _reason(): the
    LLM request must ask for plain text, not the JSON-schema
    -constrained structured decision _reason() uses -- a structured
    response can't be meaningfully streamed token-by-token.
    """

    async def fake_stream(**_kwargs):
        yield LLMStreamChunkDTO(content="Answer.", is_final=True, finish_reason="stop")

    llm_client.stream = MagicMock(side_effect=fake_stream)

    async for _ in agent.stream_final_answer(request=mock_request):
        pass

    sent_request = llm_client.stream.call_args.kwargs["request"]

    assert sent_request.inference.structured_output is False
