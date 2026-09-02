"""
Unit tests for LegalAgent.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from agentic.agents.legal import LegalAgent
from core.dto.message import MessageDTO
from core.enums import MessageRoleEnum
from core.models.agent import AgentResponseSchema
from tests.builders.agentic.agent import build_agent_request


def build_agent_response(
    *,
    content: str = "Hello!",
) -> AgentResponseSchema:
    """
    Build a valid structured agent response for tests.

    The current AgentResponseSchema requires action to be
    explicitly provided, even when no action is required.
    """

    return AgentResponseSchema(
        content=content,
        action=None,
        metadata={},
    )


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
async def test_run_calls_generate_structured(
    legal_agent: LegalAgent,
    mock_llm_client,
) -> None:
    """
    It should invoke the structured LLM generation method.
    """

    mock_llm_client.generate_structured = AsyncMock(
        return_value=build_agent_response(
            content="Hello!",
        ),
    )

    request = build_agent_request(
        instruction="Answer the user's legal question.",
    )

    response = await legal_agent.run(
        request=request,
    )

    mock_llm_client.generate_structured.assert_awaited_once()

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

    mock_llm_client.generate_structured = AsyncMock(
        return_value=build_agent_response(),
    )

    request = build_agent_request(
        instruction="Answer the user's legal question.",
    )

    await legal_agent.run(
        request=request,
    )

    llm_request = mock_llm_client.generate_structured.await_args.kwargs["request"]

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

    mock_llm_client.generate_structured = AsyncMock(
        return_value=build_agent_response(),
    )

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

    await legal_agent.run(
        request=request,
    )

    llm_request = mock_llm_client.generate_structured.await_args.kwargs["request"]

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
    It should map the structured LLM response
    to an agent response.
    """

    mock_llm_client.generate_structured = AsyncMock(
        return_value=build_agent_response(
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


@pytest.mark.asyncio
async def test_run_passes_retrieved_context_to_the_prompt(
    legal_agent: LegalAgent,
    mock_llm_client,
    mock_retriever,
) -> None:
    """It should use the Tool.execute interface and include RAG content."""

    mock_retriever.execute = AsyncMock(return_value="Relevant contract clause.")
    mock_llm_client.generate_structured = AsyncMock(return_value=build_agent_response())

    await legal_agent.run(
        request=build_agent_request(
            instruction="Answer the user's legal question.",
        ),
    )

    mock_retriever.execute.assert_awaited_once_with(query="Hello")

    llm_request = mock_llm_client.generate_structured.await_args.kwargs["request"]
    assert "Relevant contract clause." in [message.content for message in llm_request.messages]
