"""
Builders for AI agent domain models.
"""

from __future__ import annotations

from typing import Any

from src.core.enums import MessageRole
from src.core.models.agent import (
    AgentContext,
    AgentRequest,
    AgentResponse,
    AgentStreamChunk,
)
from src.core.models.conversation import Conversation
from src.core.models.message import Message
from src.core.models.tool import ToolFile


def build_agent_request(
    *,
    messages: list[Message] | None = None,
    uploaded_files: tuple[ToolFile, ...] = (),
    metadata: dict[str, object] | None = None,
) -> AgentRequest:
    """
    Build an AgentRequest.
    """

    conversation = Conversation(
        messages=tuple(
            messages
            or [
                Message(
                    role=MessageRole.USER,
                    content="Hello",
                ),
            ],
        ),
    )

    return AgentRequest(
        conversation=conversation,
        context=AgentContext(
            uploaded_files=uploaded_files,
            metadata=metadata or {},
        ),
    )


def build_agent_response(
    *,
    content: str = "Hello",
    metadata: dict[str, Any] | None = None,
) -> AgentResponse:
    """
    Build an AgentResponse.
    """

    return AgentResponse(
        content=content,
        metadata=metadata or {},
    )


def build_agent_stream_chunk(
    *,
    content: str = "Hello",
    is_final: bool = False,
    finish_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AgentStreamChunk:
    """
    Build an AgentStreamChunk.
    """

    return AgentStreamChunk(
        content=content,
        is_final=is_final,
        finish_reason=finish_reason,
        metadata=metadata or {},
    )
