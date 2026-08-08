"""
Unit tests for agent domain models.
"""

from __future__ import annotations

from src.core.enums import MessageRole
from src.core.models.agent import (
    AgentContext,
    AgentMetadata,
    AgentRequest,
    AgentResponse,
    AgentStreamChunk,
)
from src.core.models.conversation import Conversation
from src.core.models.message import Message
from src.core.models.tool import ToolFile


def build_conversation() -> Conversation:
    """
    Build a test conversation.
    """

    return Conversation(
        messages=(
            Message(
                role=MessageRole.USER,
                content="Hello",
            ),
        ),
    )


def test_agent_context_defaults() -> None:
    """
    It should use empty runtime context by default.
    """

    context = AgentContext()

    assert context.uploaded_files == ()
    assert context.metadata == {}


def test_agent_context_accepts_uploaded_files() -> None:
    """
    It should accept uploaded files.
    """

    file = ToolFile(
        filename="contract.pdf",
        content=b"contract content",
        content_type="application/pdf",
    )

    context = AgentContext(
        uploaded_files=(file,),
        metadata={
            "source": "test",
        },
    )

    assert context.uploaded_files == (file,)
    assert context.metadata == {
        "source": "test",
    }


def test_agent_request_defaults_context() -> None:
    """
    It should default the agent context.
    """

    conversation = build_conversation()

    request = AgentRequest(
        conversation=conversation,
    )

    assert request.conversation is conversation
    assert request.context.uploaded_files == ()
    assert request.context.metadata == {}


def test_agent_request_accepts_context() -> None:
    """
    It should accept runtime context.
    """

    conversation = build_conversation()

    context = AgentContext(
        metadata={
            "source": "test",
        },
    )

    request = AgentRequest(
        conversation=conversation,
        context=context,
    )

    assert request.conversation is conversation
    assert request.context is context


def test_agent_response_defaults_metadata() -> None:
    """
    It should default metadata to an empty dictionary.
    """

    response = AgentResponse(
        content="Hello",
    )

    assert response.content == "Hello"
    assert response.metadata == {}


def test_agent_response_accepts_metadata() -> None:
    """
    It should accept response metadata.
    """

    metadata = {
        "provider": "groq",
        "model": "llama",
    }

    response = AgentResponse(
        content="Legal answer",
        metadata=metadata,
    )

    assert response.content == "Legal answer"
    assert response.metadata == metadata


def test_agent_stream_chunk_defaults() -> None:
    """
    It should use the default streaming values.
    """

    chunk = AgentStreamChunk()

    assert chunk.content == ""
    assert chunk.is_final is False
    assert chunk.finish_reason is None
    assert chunk.metadata == {}


def test_agent_stream_chunk_accepts_values() -> None:
    """
    It should accept streaming values.
    """

    chunk = AgentStreamChunk(
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

    metadata = AgentMetadata(
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

    metadata = AgentMetadata(
        name="legal",
        description="Legal assistant.",
        capabilities=("legal_qa",),
    )

    assert metadata.tools == ()
