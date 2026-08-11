"""
Builders for AI agent domain models.
"""

from __future__ import annotations

from typing import Any

from src.core.dto.agent import (
    AgentContextDTO,
    AgentRequestDTO,
    AgentResponseDTO,
    AgentStreamChunkDTO,
)
from src.core.dto.conversation import ConversationDTO
from src.core.dto.message import MessageDTO
from src.core.dto.tool import ToolFileDTO
from src.core.enums import MessageRoleEnum


def build_agent_request(
    *,
    messages: list[MessageDTO] | None = None,
    instruction: str = "Answer the user's legal question.",
    uploaded_files: tuple[ToolFileDTO, ...] = (),
    metadata: dict[str, object] | None = None,
) -> AgentRequestDTO:
    """
    Build an AgentRequestDTO.
    """

    conversation = ConversationDTO(
        messages=tuple(
            messages
            or [
                MessageDTO(
                    role=MessageRoleEnum.USER,
                    content="Hello",
                ),
            ],
        ),
    )

    return AgentRequestDTO(
        conversation=conversation,
        instruction=instruction,
        context=AgentContextDTO(
            uploaded_files=uploaded_files,
            metadata=metadata or {},
        ),
    )


def build_agent_response(
    *,
    agent_name: str = "legal",
    content: str = "Hello",
    metadata: dict[str, Any] | None = None,
) -> AgentResponseDTO:
    """
    Build an AgentResponseDTO.
    """

    return AgentResponseDTO(
        content=content,
        agent_name=agent_name,
        metadata=metadata or {},
    )


def build_agent_stream_chunk(
    *,
    content: str = "Hello",
    is_final: bool = False,
    finish_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AgentStreamChunkDTO:
    """
    Build an AgentStreamChunkDTO.
    """

    return AgentStreamChunkDTO(
        content=content,
        is_final=is_final,
        finish_reason=finish_reason,
        metadata=metadata or {},
    )
