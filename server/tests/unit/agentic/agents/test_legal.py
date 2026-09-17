from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agentic.agents.legal import LegalAgent
from agentic.decisions.schemas import AgentDecision
from core.dto.message import MessageDTO
from core.enums import MessageRoleEnum
from tests.builders.agentic.agent import build_agent_request


def build_legal_agent(mock_llm_client) -> LegalAgent:
    """Build LegalAgent using its current constructor contract."""
    return LegalAgent(llm_client=mock_llm_client)


def test_init_sets_dependencies(mock_llm_client) -> None:
    """LegalAgent owns the LLM, prompt builder, and inference policy."""
    legal_agent = build_legal_agent(mock_llm_client)

    assert legal_agent.llm is mock_llm_client
    assert legal_agent._prompt_builder is not None
    assert not hasattr(legal_agent, "_retriever")


@pytest.mark.asyncio
async def test_reason_calls_generate_structured(mock_llm_client) -> None:
    """_reason() should invoke structured decision generation."""
    decision = object()
    mock_llm_client.generate_structured = AsyncMock(
        return_value=decision,
    )

    legal_agent = build_legal_agent(mock_llm_client)
    request = build_agent_request(
        instruction="Answer the user's legal question.",
    )

    result = await legal_agent._reason(request=request)

    mock_llm_client.generate_structured.assert_awaited_once()

    kwargs = mock_llm_client.generate_structured.await_args.kwargs
    assert kwargs["response_model"] is AgentDecision
    assert result is decision


@pytest.mark.asyncio
async def test_reason_passes_expected_messages(mock_llm_client) -> None:
    """_reason() should build the expected provider-independent messages."""
    mock_llm_client.generate_structured = AsyncMock(
        return_value=object(),
    )

    legal_agent = build_legal_agent(mock_llm_client)
    request = build_agent_request(
        instruction="Answer the user's legal question.",
    )

    await legal_agent._reason(request=request)

    llm_request = mock_llm_client.generate_structured.await_args.kwargs["request"]
    messages = llm_request.messages

    assert messages[0].role is MessageRoleEnum.SYSTEM
    assert messages[0].content == legal_agent._prompt_builder._system_prompt

    assert messages[-1].role is MessageRoleEnum.USER
    assert messages[-1].content == "Hello"


@pytest.mark.asyncio
async def test_reason_includes_history(mock_llm_client) -> None:
    """_reason() should preserve conversation history in the prompt."""
    mock_llm_client.generate_structured = AsyncMock(
        return_value=object(),
    )

    legal_agent = build_legal_agent(mock_llm_client)
    request = build_agent_request(
        instruction="Answer the current legal question.",
        messages=[
            MessageDTO(
                role=MessageRoleEnum.USER,
                content="Old question",
            ),
            MessageDTO(
                role=MessageRoleEnum.ASSISTANT,
                content="Old answer",
            ),
            MessageDTO(
                role=MessageRoleEnum.USER,
                content="Current question",
            ),
        ],
    )

    await legal_agent._reason(request=request)

    llm_request = mock_llm_client.generate_structured.await_args.kwargs["request"]
    contents = [message.content for message in llm_request.messages]

    assert "Old question" in contents
    assert "Old answer" in contents
    assert "Current question" in contents


@pytest.mark.asyncio
async def test_reason_returns_agent_decision(mock_llm_client) -> None:
    """_reason() should return the structured AgentDecision unchanged."""
    decision = object()
    mock_llm_client.generate_structured = AsyncMock(
        return_value=decision,
    )

    legal_agent = build_legal_agent(mock_llm_client)

    result = await legal_agent._reason(
        request=build_agent_request(
            instruction="Provide a legal answer.",
        ),
    )

    assert result is decision
