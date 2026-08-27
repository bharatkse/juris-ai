"""
Unit tests for agent domain models.
"""

from __future__ import annotations

from core.dto.agent import (
    AgentMetadataDTO,
    AgentRequestDTO,
    AgentResponseDTO,
    AgentStreamChunkDTO,
)
from core.dto.conversation import ConversationDTO
from core.dto.message import MessageDTO
from core.dto.tool import ToolFileDTO
from core.enums import MessageRoleEnum
from tests.builders.agentic.agent import build_agent_context


def build_conversation() -> ConversationDTO:
    """
    Build a test conversation.
    """

    return ConversationDTO(
        messages=(
            MessageDTO(
                role=MessageRoleEnum.USER,
                content="Hello",
            ),
        ),
    )


def test_agent_context_defaults() -> None:
    """
    It should use empty runtime context by default.
    """

    context = build_agent_context()

    assert context.uploaded_files == ()
    assert context.metadata == {}


def test_agent_context_accepts_uploaded_files() -> None:
    """
    It should accept uploaded files.
    """

    file = ToolFileDTO(
        filename="contract.pdf",
        content=b"contract content",
        content_type="application/pdf",
    )

    context = build_agent_context(
        uploaded_files=(file,),
        metadata={
            "source": "test",
        },
    )

    assert context.uploaded_files == (file,)
    assert context.metadata == {
        "source": "test",
    }


def test_agent_request_requires_instruction() -> None:
    """
    It should require an agent instruction.
    """

    conversation = build_conversation()

    request = AgentRequestDTO(
        conversation=conversation,
        instruction="Answer the user's legal question.",
        context=build_agent_context(),
    )

    assert request.conversation is conversation
    assert request.instruction == "Answer the user's legal question."
    assert request.context.uploaded_files == ()
    assert request.context.metadata == {}


def test_agent_request_accepts_context() -> None:
    """
    It should accept runtime context.
    """

    conversation = build_conversation()

    context = build_agent_context(
        metadata={
            "source": "test",
        },
    )

    request = AgentRequestDTO(
        conversation=conversation,
        instruction="Analyze the legal question.",
        context=context,
    )

    assert request.conversation is conversation
    assert request.instruction == "Analyze the legal question."
    assert request.context is context


def test_agent_response_requires_agent_name() -> None:
    """
    It should require the agent name.
    """

    response = AgentResponseDTO(
        content="Hello",
        agent_name="legal",
    )

    assert response.content == "Hello"
    assert response.agent_name == "legal"
    assert response.metadata == {}


def test_agent_response_accepts_metadata() -> None:
    """
    It should accept response metadata.
    """

    metadata = {
        "provider": "groq",
        "model": "llama",
    }

    response = AgentResponseDTO(
        content="Legal answer",
        agent_name="legal",
        metadata=metadata,
    )

    assert response.content == "Legal answer"
    assert response.agent_name == "legal"
    assert response.metadata == metadata


def test_agent_response_accepts_citations_and_sources() -> None:
    """
    It should accept citations and sources.
    """

    response = AgentResponseDTO(
        content="Legal answer",
        agent_name="legal",
        citations=(),
        sources=(),
    )

    assert response.content == "Legal answer"
    assert response.agent_name == "legal"
    assert response.citations == ()
    assert response.sources == ()
    assert response.usage is None


def test_agent_stream_chunk_defaults() -> None:
    """
    It should use the default streaming values.
    """

    chunk = AgentStreamChunkDTO()

    assert chunk.content == ""
    assert chunk.is_final is False
    assert chunk.finish_reason is None
    assert chunk.metadata == {}


def test_agent_stream_chunk_accepts_values() -> None:
    """
    It should accept streaming values.
    """

    chunk = AgentStreamChunkDTO(
        content="Hello",
        is_final=True,
        finish_reason="stop",
        metadata={
            "provider": "groq",
        },
    )

    assert chunk.content == "Hello"
    assert chunk.is_final is True
    assert chunk.finish_reason == "stop"
    assert chunk.metadata == {
        "provider": "groq",
    }


def test_agent_metadata_accepts_values() -> None:
    """
    It should describe an agent.
    """

    metadata = AgentMetadataDTO(
        name="legal",
        description="General-purpose legal assistant.",
        capabilities=(
            "legal_research",
            "legal_qa",
        ),
        tools=("retriever",),
    )

    assert metadata.name == "legal"
    assert metadata.description == "General-purpose legal assistant."
    assert metadata.capabilities == (
        "legal_research",
        "legal_qa",
    )
    assert metadata.tools == ("retriever",)


def test_agent_metadata_defaults_tools() -> None:
    """
    It should default tools to an empty tuple.
    """

    metadata = AgentMetadataDTO(
        name="legal",
        description="Legal assistant.",
        capabilities=("legal_qa",),
    )

    assert metadata.tools == ()
