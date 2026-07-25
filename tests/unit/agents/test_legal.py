"""
Unit tests for LegalAgent.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.agents.legal import LegalAgent
from src.agents.legal_stream import LegalAgentStream
from src.clients.models import LLMMessage
from src.core.enums import MessageRole
from tests.builders.agent import build_agent_request
from tests.builders.llm import build_llm_response


def test_init_sets_dependencies(
    legal_agent: LegalAgent,
    mock_llm_client,
) -> None:
    """
    It should initialize the agent.
    """

    assert legal_agent._client is mock_llm_client
    assert legal_agent._system_prompt


@pytest.mark.asyncio
async def test_answer_calls_generate(
    legal_agent: LegalAgent,
    mock_llm_client,
) -> None:
    """
    It should invoke the LLM client.
    """

    mock_llm_client.generate = AsyncMock(
        return_value=build_llm_response(),
    )

    await legal_agent.answer(
        request=build_agent_request(),
    )

    mock_llm_client.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_answer_passes_expected_messages(
    legal_agent: LegalAgent,
    mock_llm_client,
) -> None:
    """
    It should build the expected prompt.
    """

    request = build_agent_request()

    mock_llm_client.generate = AsyncMock(
        return_value=build_llm_response(),
    )

    await legal_agent.answer(
        request=request,
    )

    kwargs = mock_llm_client.generate.await_args.kwargs

    messages = kwargs["messages"]

    assert len(messages) == 2

    assert messages[0] == LLMMessage(
        role=MessageRole.SYSTEM,
        content=legal_agent._system_prompt,
    )

    assert messages[-1] == LLMMessage(
        role=MessageRole.USER,
        content=request.question,
    )


@pytest.mark.asyncio
async def test_answer_includes_history(
    legal_agent: LegalAgent,
    mock_llm_client,
) -> None:
    """
    It should include conversation history.
    """

    request = build_agent_request(
        history=[
            LLMMessage(
                role=MessageRole.USER,
                content="Old question",
            ),
            LLMMessage(
                role=MessageRole.ASSISTANT,
                content="Old answer",
            ),
        ],
    )

    mock_llm_client.generate = AsyncMock(
        return_value=build_llm_response(),
    )

    await legal_agent.answer(
        request=request,
    )

    messages = mock_llm_client.generate.await_args.kwargs["messages"]

    assert len(messages) == 4

    assert messages[1].content == "Old question"
    assert messages[2].content == "Old answer"


@pytest.mark.asyncio
async def test_answer_uses_temperature(
    legal_agent: LegalAgent,
    mock_llm_client,
) -> None:
    """
    It should use the configured temperature.
    """

    mock_llm_client.generate = AsyncMock(
        return_value=build_llm_response(),
    )

    await legal_agent.answer(
        request=build_agent_request(),
    )

    kwargs = mock_llm_client.generate.await_args.kwargs

    assert kwargs["temperature"] == 0.2


@pytest.mark.asyncio
async def test_answer_returns_agent_response(
    legal_agent: LegalAgent,
    mock_llm_client,
) -> None:
    """
    It should map the LLM response.
    """

    mock_llm_client.generate = AsyncMock(
        return_value=build_llm_response(
            content="Legal answer",
        ),
    )

    response = await legal_agent.answer(
        request=build_agent_request(),
    )

    assert response.content == "Legal answer"
    assert response.provider == mock_llm_client.provider
    assert response.model == mock_llm_client.model
    assert response.latency_ms >= 0


def test_stream_answer_returns_legal_agent_stream(
    legal_agent: LegalAgent,
) -> None:
    """
    It should create a LegalAgentStream.
    """

    stream = legal_agent.stream_answer(
        build_agent_request(),
    )

    assert isinstance(
        stream,
        LegalAgentStream,
    )


def test_stream_answer_uses_same_client(
    legal_agent: LegalAgent,
    mock_llm_client,
) -> None:
    """
    It should reuse the configured client.
    """

    stream = legal_agent.stream_answer(
        build_agent_request(),
    )

    assert stream._client is mock_llm_client


def test_stream_answer_builds_messages(
    legal_agent: LegalAgent,
) -> None:
    """
    It should build the expected messages.
    """

    request = build_agent_request()

    stream = legal_agent.stream_answer(
        request,
    )

    assert len(stream._messages) == 2

    assert stream._messages[0].role == MessageRole.SYSTEM
    assert stream._messages[-1].role == MessageRole.USER
