"""
Builders for AI agent domain models.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from src.core.dto.agent import (
    AgentActionRequestDTO,
    AgentContextDTO,
    AgentRequestDTO,
    AgentResponseDTO,
    AgentStreamChunkDTO,
)
from src.core.dto.message import MessageDTO
from src.core.dto.tool import ToolFileDTO
from src.core.enums import ActionTypeEnum, ActorTypeEnum
from tests.builders.conversation import build_conversation


def build_agent_context(
    *,
    execution_id: str = None,
    uploaded_files: tuple[str, ...] = (),
    metadata: dict[str, Any] | None = None,
    user_id: str = None,
    conversation_event_id: str = None,
    thread_id: str = None,
) -> AgentContextDTO:
    return AgentContextDTO(
        execution_id=execution_id or str(uuid4()),
        thread_id=thread_id or str(uuid4()),
        conversation_event_id=conversation_event_id or str(uuid4()),
        uploaded_files=uploaded_files,
        metadata=metadata or {},
        user_id=user_id or str(uuid4()),
    )


def build_agent_action_request_dto(
    *,
    execution_id: str = "execution-123",
    thread_id: str = "thread-123",
    conversation_event_id: str = "conversation-event-123",
    agent_id: str = "agent-123",
    action_type: ActionTypeEnum = ActionTypeEnum.TOOL_CALL,
    actor_type: ActorTypeEnum = ActorTypeEnum.USER,
    tool_name: str | None = None,
    target_agent_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    parameters: dict[str, Any] | None = None,
    reason: str = "",
) -> AgentActionRequestDTO:
    return AgentActionRequestDTO(
        execution_id=execution_id,
        thread_id=thread_id,
        conversation_event_id=conversation_event_id,
        agent_id=agent_id,
        action_type=action_type,
        actor_type=actor_type,
        tool_name=tool_name,
        target_agent_id=target_agent_id,
        resource_type=resource_type,
        resource_id=resource_id,
        parameters=parameters or {},
        reason=reason,
    )


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

    return AgentRequestDTO(
        conversation=build_conversation(messages=messages),
        instruction=instruction,
        context=build_agent_context(
            uploaded_files=uploaded_files,
            metadata=metadata,
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
