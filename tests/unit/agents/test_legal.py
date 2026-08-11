"""
Unit tests for LegalAgent.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.agents.legal import LegalAgent
from src.core.dto.message import MessageDTO
from src.core.enums import MessageRoleEnum
from tests.builders.agent import build_agent_request
from tests.builders.clients.llm import build_llm_response


def test_init_sets_dependencies(
    legal_agent: LegalAgent,
    mock_llm_client,
) -> None:
    """
    It should initialize the agent dependencies.
    """

    assert legal_agent.llm is mock_llm_client
    assert legal_agent._prompt_builder is not None
    assert legal_agent._retriever is not None


@pytest.mark.asyncio
async def test_run_calls_generate(
    legal_agent: LegalAgent,
    mock_llm_client,
) -> None:
    """
    It should invoke the LLM client.
    """

    mock_llm_client.generate = AsyncMock(
        return_value=build_llm_response(),
    )

    request = build_agent_request(
        instruction="Answer the user's legal question.",
    )

    response = await legal_agent.run(
        request=request,
    )

    mock_llm_client.generate.assert_awaited_once()

    assert response.content == "Hello!"
    assert response.agent_name == legal_agent.metadata.name


@pytest.mark.asyncio
async def test_run_passes_expected_messages(
    legal_agent: LegalAgent,
    mock_llm_client,
) -> None:
    """
    It should build the expected LLM messages.
    """

    request = build_agent_request(
        instruction="Answer the user's legal question.",
    )

    mock_llm_client.generate = AsyncMock(
        return_value=build_llm_response(),
    )

    await legal_agent.run(
        request=request,
    )

    llm_request = mock_llm_client.generate.await_args.kwargs["request"]

    messages = llm_request.messages

    assert messages[0].role is MessageRoleEnum.SYSTEM
    assert messages[0].content == (legal_agent._prompt_builder._system_prompt)

    assert messages[-1].role is MessageRoleEnum.USER
    assert messages[-1].content == "Hello"


@pytest.mark.asyncio
async def test_run_includes_history(
    legal_agent: LegalAgent,
    mock_llm_client,
) -> None:
    """
    It should include conversation history.
    """

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

    mock_llm_client.generate = AsyncMock(
        return_value=build_llm_response(),
    )

    await legal_agent.run(
        request=request,
    )

    llm_request = mock_llm_client.generate.await_args.kwargs["request"]

    messages = llm_request.messages

    contents = [message.content for message in messages]

    assert "Old question" in contents
    assert "Old answer" in contents
    assert "Current question" in contents


@pytest.mark.asyncio
async def test_run_returns_agent_response(
    legal_agent: LegalAgent,
    mock_llm_client,
) -> None:
    """
    It should map the LLM response to an agent response.
    """

    mock_llm_client.generate = AsyncMock(
        return_value=build_llm_response(
            content="Legal answer",
        ),
    )

    response = await legal_agent.run(
        request=build_agent_request(
            instruction="Provide a legal answer.",
        ),
    )

    assert response.content == "Legal answer"
    assert response.agent_name == legal_agent.metadata.name
